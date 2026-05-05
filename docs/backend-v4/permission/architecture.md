# permission 模块 architecture.md

本文档描述 `newbee_notebook/core/permission/` 模块的内部结构与设计选择。设计严格服从 [goals-duty.md](goals-duty.md)：永久允许 DB 表的唯一读写者、内容哈希绑定许可、fail-closed、级联清理。

---

## 一、Architecture Overview（总体架构）

permission 模块由六个子组件协作完成"查已允许 → 弹卡 → 等响应 → 落地许可 → 清理"的职责：

1. **PermissionGateway（对外门面）** — 暴露 `request()` / `clear_session()` / `abort_turn()` / `reset_on_startup()` / `clear_skill_permissions()`；编排其余子组件。
2. **AllowStore（永久允许唯一读写者）** — 唯一触达 `app_settings` 表 `permissions.*` key 的组件。key 形如 `permissions.user_<uid>.<scope>.allow.<sig>`（scope 在 skill 上下文含 `@<content_hash>`）。
3. **SessionAllowCache（会话内存许可）** — 每 session_id 持有一个 set，存 `always_session` 的 signature。backend 重启即失效。
4. **ConfirmationDispatcher（弹卡协作层）** — v1 复用 [ConfirmationGateway](../../../newbee_notebook/core/engine/confirmation.py) 与 SSE `ConfirmationRequestEvent`（扩展字段，向后兼容）；v2 并入本模块。
5. **QueueManager（串行队列与取消）** — 按 `(session_id, assistant_turn_id, tool_call_id)` 键组织队列；提供"前序被拒则取消同 turn 后续"、"session 关闭清队列"、"abort 清队列"、"启动清队列"语义。
6. **DecisionRecorder（决定落地）** — 根据用户选择调 AllowStore 或 SessionAllowCache 写入；reject 时产出 typed `RejectionWithSuggestion`。

### 调用依赖

```
PermissionGateway
├── AllowStore                  （唯一 DB 读写）
├── SessionAllowCache           （进程内存）
├── ConfirmationDispatcher      （v1 用 ConfirmationGateway；v2 内置）
├── QueueManager                （串行 + 取消语义）
└── DecisionRecorder            （落地：DB / session memory / typed rejection）
```

### 请求路径（高层）

1. agent_loop 收到 policy 返回的 `ASK`，调 `PermissionGateway.request(req)`
2. 查 `SessionAllowCache(session_id, signature)` → 命中返回 allow
3. 查 `AllowStore(user=local, scope=signature_scope, sig=signature)` → 命中返回 allow
4. 都未命中：`QueueManager.enqueue(req)`
5. QueueManager 串行处理：通过 ConfirmationDispatcher 推 SSE 卡给前端
6. 用户响应经前端回到 `ConfirmationGateway.resolve`，唤醒等待
7. DecisionRecorder 按响应类型落地：`always_persist` → AllowStore 写 DB；`always_session` → SessionAllowCache；`reject_with_suggestion` → 构造 typed `RejectionWithSuggestion`
8. 返回给 agent_loop

### 取消路径

- **session 关闭 / SSE 断连** → `clear_session()` → QueueManager 清该 session 所有队列项，wait() 方返回"已取消"
- **generation abort** → `abort_turn(session_id, turn_id)` → QueueManager 清该 turn 队列
- **backend 启动** → `reset_on_startup()` → 清所有进程内 pending（fail-closed）
- **skill 卸载** → `clear_skill_permissions(name)` → AllowStore 删 `permissions.user_*.skill:<name>@*.allow.*` + SessionAllowCache 删匹配项

---

## 二、Design Pattern & Rationale（设计模式与理由）

### 1. Facade — PermissionGateway

对 agent_loop 只暴露一个门面。内部六组件的演化不影响调用方。服务于 goals-duty **G1（单一职责）**。

### 2. Single Writer — AllowStore 唯一 DB 触达

codex P1 指出 permission+policy 双查 DB 会一致性失控。**改为 AllowStore 是 `permissions.*` 表的唯一读写者**，policy 完全不读 DB。服务于 goals-duty **G2**。

### 3. Extension Over Replacement — v1 复用 ConfirmationGateway

v1 不重写确认基础设施，ConfirmationDispatcher 内部用 [ConfirmationGateway](../../../newbee_notebook/core/engine/confirmation.py) 的 asyncio Event。内置 skill（note/diagram）保留原路径不动，降低实现风险。v2 再统一迁入。服务于 goals-duty **G3 + N10**。

### 4. Queue Ownership — QueueManager 独立

codex 指出"并发 ASK 需要 request_id、取消规则、陈旧请求处理"。QueueManager 独立出来专门处理：
- 队列 key 是 `(session_id, turn_id, tool_call_id)` 三元组
- 前序 reject 取消同 turn 后续（实现"拒绝后不再用失效 plan 继续调用"）
- 会话级/turn 级/进程级三层清理语义

服务于 goals-duty **G5（并发/生命周期严格）**。

### 5. Content-Bound Allow — AllowStore 的 scope 编码

scope 在 skill 调用时编码 `skill:<name>@<content_hash>`，全局调用为 `global`。**内容变更 → content_hash 变 → scope 字符串变 → key 不命中 → 旧许可失效**。无需 permission 主动失效，天然正确。服务于 goals-duty **G4**。

### 6. Typed Rejection — DecisionRecorder 产出结构化 contract

codex 指出用 error 字符串返回建议会让 mellow 误判为执行失败。**DecisionRecorder 产出 `RejectionWithSuggestion(signature, suggestion_text)`**，由 agent_loop 翻译为 `ToolCallResult.metadata`。服务于 goals-duty **G8**。

### 7. Fail-Closed — 所有异常路径拒绝

gateway 丢失、超时、session 结束、content_hash 对不上 → 一律拒绝。不回退到 allow。服务于 goals-duty **G6**。

### 8. 未引入独立 Event Bus

codex 审核过：newbee 已有 SSE + ConfirmationGateway，足够。

---

## 三、Module Structure & File Layout（模块结构与文件组织）

```
newbee_notebook/core/permission/
├── __init__.py                     # 对外导出 PermissionGateway、UserResponse、RejectionWithSuggestion
├── gateway.py                      # PermissionGateway（Facade）
├── allow_store.py                  # AllowStore（唯一 DB 读写者，读写 app_settings permissions.*）
├── session_cache.py                # SessionAllowCache（进程内存 dict，session_id → set[signature]）
├── dispatcher.py                   # ConfirmationDispatcher（v1 复用 ConfirmationGateway；v2 内置）
├── queue_manager.py                # QueueManager（串行队列 + 取消语义 + 键 (session, turn, tool_call)）
├── recorder.py                     # DecisionRecorder（落地：调 AllowStore / SessionAllowCache / 构造 typed rejection）
└── contracts.py                    # PermissionRequest / UserResponse / RejectionWithSuggestion / ResponseKind
```

### 稳定接口 vs 内部实现

- **对外稳定**：`PermissionGateway.request / clear_session / abort_turn / reset_on_startup / clear_skill_permissions`、`contracts.py` 数据类
- **内部可演化**：`AllowStore` 具体 SQL、`QueueManager` 内部容器类型、v2 是否把 `ConfirmationGateway` 内联

### allow_store.py 关键细节

- key 格式 `permissions.user_<uid>.<scope>.allow.<sig>`；`<uid>` v1 固定 `local`
- 查询是 `app_settings.key = ?` 精确匹配；`app_settings.key` 本就是主键（见 [database.py:79](../../../newbee_notebook/infrastructure/persistence/database.py#L79)），单次查询 O(log n)
- `clear_skill_permissions` 用 `key LIKE 'permissions.%.skill:<name>@%.allow.%'` 做前缀删除

### 不包含的子组件

- **决策逻辑**：policy 模块
- **工具执行**：agent_loop
- **UI 渲染**：前端 confirmation-card
- **skill 内容哈希计算**：skills 模块

---

## 四、Architectural Constraints & Trade-offs（约束与权衡）

### 放弃方案：policy 与 permission 都查 DB

详见 Design Pattern #2。**代价**：agent_loop 在 ASK 路径上必须先过 permission（而非先查 DB 再决定是否调 permission）。但 permission 本就是 ASK 路径的唯一下一站，顺序自然。

### 放弃方案：全内存 AllowList

参考项目是全内存。newbee 需要跨会话"始终允许"持久化。采取混合策略：永久 → DB；本会话 → 内存。

### 放弃方案：永久允许仅绑 name

codex 指出此为零确认攻击面。**改为绑 content_hash**。用户侧代价：重装/更新 skill 后旧许可失效，需要再次确认；这是正确的安全代价。

### 放弃方案：permission 内部维护工具风险分级

risk_level 由 ToolDefinition 声明、policy 透传，permission 只展示给前端。

### 放弃方案：独立 Event Bus

已有 SSE + ConfirmationGateway。

### 妥协：v1 仍用 ConfirmationGateway，v2 再迁移

代价：v1 内置 skill 与用户 skill 有两条确认路径并存。好处：v1 不破坏已有业务，风险最低。

### 妥协：本会话允许仅进程内存

backend 重启丢失。与 newbee 的 web 长会话不完美，但 fail-closed 语义优先。

### 妥协：user_id 固定 `local`

v1 单用户假设，key 已预留 user_id 槽位，v2 升级无需迁移。

### 可演进性

- v2：内联 ConfirmationGateway，移除与内置 skill 的共存期
- 未来审计：在 AllowStore 增加 `permissions.audit.*` key 或独立表，记录每次许可生效；不破坏现有 API
- 未来短期粒度（"5 分钟内允许"）：SessionAllowCache 加 TTL 维度
