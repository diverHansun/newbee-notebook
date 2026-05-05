# permission 模块 non-functional.md

本文档说明 permission 模块在功能正确性之外必须满足的工程约束。设计基于 [goals-duty.md](goals-duty.md) 与 [architecture.md](architecture.md)。

permission 处于 agent_loop 的**关键路径**：每次 ASK 决策都经它，每次 ALLOW 也至少经一次 AllowStore 查询。它持有持久化白名单（DB 唯一写者）、跨会话内存状态、SSE 事件链路三个维度的责任，是模块体系中最容易出现一致性/泄漏问题的位置。

---

## 一、Quality Priorities（质量优先级）

按优先级从高到低：

1. **Fail-closed 正确性 > 一切**
   异常路径（gateway 丢失、超时、session 结束、内容哈希对不上、DB 写入失败、SSE 推送失败）一律拒绝。**永不**因方便降级到 allow。代价：用户偶尔需要重试一次确认，可接受。

2. **永久 allow 写入的事务正确性**
   "用户点了 always_persist 但 DB 写失败却返回了 allow" 是不可接受的——必须先写 DB 成功，再返回 allow。这是 permission 是 DB **单一写者**的核心承诺。

3. **响应延迟 < 一致性**
   ASK 路径的延迟（用户等待）允许包含一次 DB 查询 + 一次 SSE 往返；ALLOW 路径（已允许命中）必须 ≤ 5ms。永不为了"快"而绕过 DB 查 cache。

4. **可观测性 > 性能极致**
   所有失败路径产生结构化日志（含 signature、scope、user_id、原因）；性能优化让位于"出问题时能查清楚"。

5. **简单性 > 通用性**
   v1 不为多用户、多审计后端、复杂粒度（"5 分钟内允许"）做设计——单 user_id="local" 假设 + 进程内 SessionAllowCache + DB 永久 allow 已足够。

---

## 二、Operational Constraints（运行约束）

### 调用频次

- ASK 路径：与用户交互节奏一致，每分钟 ≤ 几十次/会话；不会成为吞吐瓶颈
- ALLOW 路径（已允许）：与工具调用频率一致，agent_loop 每个 turn 可能数十次；必须低延迟

### 延迟与查询

- AllowStore 单次查询：`app_settings.key` 主键精确匹配，DB 已有 `PRIMARY KEY (key)` 约束（参见 [database.py:79](../../../newbee_notebook/infrastructure/persistence/database.py#L79)），单次查询 < 1ms（本机 PG）
- ALLOW 命中路径总延迟（含 SessionAllowCache + AllowStore）：≤ 5ms p99
- ASK 弹卡到用户响应：受用户决策时间主导，不在工程约束范围；agent_loop 已有 180s 超时兜底

### 并发与队列

- 同一 session 同一时刻仅一个待确认（QueueManager 串行化）
- 不同 session 之间并发无限制（每个 session 独立队列）
- SessionAllowCache 占用：`O(active_sessions × avg_session_allows)`，单 session 上限 100 条 entries（超出时 LRU 淘汰，但 always_persist 永不淘汰因为不在内存）

### 资源占用

- 进程内存：v1 不限 SessionAllowCache 大小（按上述上限自然受控）；监控 OOM 风险
- DB：`permissions.*` key 数量随用户许可增长，预期 < 1000 entries/月，不构成压力
- SSE 流量：每次 ASK 一次事件，payload < 4KB，可忽略

### 外部依赖稳定性

- DB 不可达：永久 allow 写入失败 → ASK 路径返回 typed `PersistenceFailure`，不放行；ALLOW 路径（已命中查询）失败 → 退化为"未命中"，进入 ASK 流程（fail-closed）
- SSE 通道断开：`clear_session(sid)` 触发，所有 pending wait() 解除并返回 cancellation；不重试推卡
- ConfirmationGateway（v1 复用）异常：透传为 `GatewayLost` 错误

---

## 三、Reliability & Observability（可靠性与可观测性）

### 失败容忍

| 失败类型 | 行为 | 用户感知 |
|---|---|---|
| AllowStore 读失败 | 退化为"未命中"，进入 ASK | 多一次确认 |
| AllowStore 写失败（always_persist） | 返回 `PersistenceFailure`，不放行 | 工具调用被拒，用户可重试 |
| SSE 推送失败 | 立即返回拒绝 | 工具调用被拒 |
| backend 重启 | reset_on_startup 清所有 pending wait() | 所有进行中确认被取消，agent_loop 重新规划 |
| generation abort | abort_turn 清队列 | 用户停止生成时所有待确认即刻消失 |
| 用户 SSE 断连 | clear_session 清队列 | 用户重连后看不到旧卡片 |

### 不可接受的失败

- **静默放行**：任何"DB 没写但返回 allow"的路径
- **许可继承**：skill 内容变更后旧 sig 仍命中（由 content_hash 在 scope 中编码自然防护）
- **悬挂 wait()**：进程重启后仍有 asyncio Event 等待（reset_on_startup 强制清理）
- **跨 session 泄漏**：A session 的 always_session 被 B session 命中（SessionAllowCache 严格按 session_id 隔离）

### 结构化日志

每次 `request()` 调用记录一条 INFO/WARN 级别日志（JSON 行）：
- `session_id` / `assistant_turn_id` / `tool_call_id`
- `signature`（脱敏：仅记 scope 与 tool 名，不记 arg_hash 完整值）
- `outcome`：`allow_cached_db` / `allow_cached_session` / `asked_user_<response>` / `failed_<reason>`
- `latency_ms`

每次 `clear_skill_permissions(name)` 记录 INFO：删除 entry 数 + skill 名。

不进 audit 表（v1）。日志走 newbee 标准 logger，由现有日志基础设施（stdout / 文件 / journald）收集。

### 指标（v2 预留，v1 不做）

未来需要时通过 Prometheus 暴露：`permission_request_total{outcome}`、`permission_request_latency_ms`、`permission_db_write_failures_total`。

---

## 四、Trade-offs & Deferred Requirements（权衡与暂缓项）

### 当前阶段不做

1. **多用户隔离**
   user_id 字段在 key 中占位为 `local`。多用户部署需另外设计——v1 假设 newbee 是单用户本地工具。
   原因：单用户场景占绝对多数；为多用户做完整 ACL 会显著放大复杂度。

2. **审计后端**
   不写 `permission_audit` 表，不做"谁在什么时候批准了什么"的可查历史。
   原因：v1 用日志足够追溯；做审计表需考虑保留策略、查询 API、合规导出，与当前体量不匹配。

3. **细粒度时间窗（"5 分钟内允许"）**
   只支持 `once / always_session / always_persist / reject` 四档。
   原因：YAGNI——尚无场景证明用户会需要"15 分钟内不再问"。

4. **回声机制 / 缓存同步**
   policy 不持有 allow 缓存，每次自己读 DB（已在 policy 模块决定）。permission 写完不通知任何模块。
   原因：消除缓存一致性问题，DB 主键查询 < 1ms 不构成性能压力。

5. **响应级超时**
   permission 不实现"用户 N 秒不响应自动拒绝"。agent_loop 的 180s 兜底足够。
   原因：用户决策时间天然多变；过早超时会误伤慢思考。

6. **完整指标导出**
   v1 仅日志。指标接口预留但不实现。

### 已接受的代价

- backend 重启 → 进行中确认全部取消，需用户重做 → 影响开发期 hot reload 体验，可接受
- always_persist 写 DB 失败 → 整次工具调用拒绝 → 在 DB 不稳定时用户体验下降，但 fail-closed 正确性优先
- 单用户假设 → 多用户场景需未来重新设计 → 接受
