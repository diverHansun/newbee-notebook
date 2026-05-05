# permission 模块 test.md

本文档说明如何验证 `newbee_notebook/core/permission/` 模块在真实协作环境中的正确性。设计基于 [goals-duty.md](goals-duty.md)、[architecture.md](architecture.md)、[dfd-interface.md](dfd-interface.md)。

---

## 一、Module Test Profile（模块测试档案）

- **模块原型**：服务编排模块
- **主要测试类型**：unit + integration
- **Mock 边界**：
  - AllowStore（DB 操作）：integration 用真实内存 SQLite，unit 用 mock
  - ConfirmationDispatcher（SSE + ConfirmationGateway）：unit 用 mock；integration 用真实 SSE 通道
  - SessionAllowCache：unit 直接操作内存 dict，无需 mock
  - QueueManager：unit 直接操作内部队列，无需 mock
  - 前端确认卡渲染：不覆盖（前端测试范围）
- **测试归属目录**：`tests/unit/core/permission/` + `tests/integration/core/permission/`

---

## 二、Test Scope（测试范围）

### 覆盖

- `PermissionGateway.request()` 的完整编排流程（查缓存 → 查 DB → 入队 → 弹卡 → 等响应 → 落地）
- AllowStore 的永久 allow 读写正确性（含 scope 编码与 DB key 格式）
- SessionAllowCache 的会话级许可生命周期
- QueueManager 的串行化、取消语义（session 关闭、abort、前序拒绝级联）
- ConfirmationDispatcher 的 SSE 事件推送（字段扩展与向后兼容）
- DecisionRecorder 的四种响应落地（once / always_session / always_persist / reject_with_suggestion）
- 级联清理路径：`clear_session` / `abort_turn` / `reset_on_startup` / `clear_skill_permissions`
- Fail-closed 语义（DB 写失败、gateway 丢失、超时、session 结束等异常路径）

### 不覆盖

- policy 的 ALLOW/ASK/DENY 决策逻辑（属于 policy 的测试范围）
- 前端确认卡 UI 渲染与交互（属于前端测试范围）
- ConfirmationGateway 的底层 asyncio Event 实现（属于现有模块的测试）
- ToolDefinition 的 risk_level 声明（属于 core/tools 的测试范围）
- agent_loop 如何调 permission 及处理返回值（属于 agent_loop 的测试范围）

---

## 三、Critical Scenarios（关键场景）

### 正常路径

| # | 场景 | 输入 | 预期结果 |
|---|------|------|---------|
| 1 | SessionAllowCache 命中 → 直接 allow | signature 已在 session 内存中 | UserResponse.kind="allow"，不查 DB，不弹卡 |
| 2 | AllowStore（DB）命中 → 直接 allow | DB 中有 `permissions.user_local.global.allow.<sig>` | UserResponse.kind="allow"，不弹卡 |
| 3 | 未命中 → 弹卡 → 用户选 once | 新 signature，用户选 "仅本次" | UserResponse.kind="allow"，不写任何持久记录 |
| 4 | 未命中 → 弹卡 → 用户选 always_session | 新 signature，用户选 "本会话始终" | SessionAllowCache 写入，后续同 session 同 sig 路径 1 命中 |
| 5 | 未命中 → 弹卡 → 用户选 always_persist | 新 signature，用户选 "始终允许" | AllowStore 写 DB 成功 → UserResponse.kind="allow" |

### 异常路径

| # | 场景 | 预期结果 |
|---|------|---------|
| 6 | always_persist 但 DB 写失败 | 返回 UserResponse.kind="deny"，reason 含 "PersistenceFailure" |
| 7 | SSE 通道断开 | ConfirmationDispatcher 推卡失败 → 返回拒绝，不重试 |
| 8 | ConfirmationGateway 超时/丢失 | wait() 超时 → 返回拒绝（fail-closed） |
| 9 | PermissionRequest 中 session 已关闭 | QueueManager 拒绝入队 → 返回拒绝 |
| 10 | 同 assistant_turn 前序被 reject → 后续自动拒 | 后续同 turn 的 request 不入队，直接返回 reject |
| 11 | AllowStore 读失败（DB 不可达） | 退化为 "未命中"，进入弹卡路径（而非抛异常） |

### 级联清理

| # | 场景 | 预期结果 |
|---|------|---------|
| 12 | clear_session：session 关闭 | 该 session 所有 queue pending 取消 + SessionAllowCache 清空 + wait() 返回 cancelled |
| 13 | abort_turn：generation abort | 该 turn 的 queue pending 取消 + 后续同 turn 排队者解除 |
| 14 | reset_on_startup：backend 重启 | 所有进程内 pending 清空 + 所有 SessionAllowCache 清空 |
| 15 | clear_skill_permissions：skill 卸载 | AllowStore 中 `permissions.*.skill:<name>@%.allow.%` 全部删除 + 所有 session 内存中匹配项清除 |

### 拒绝建议 typed 返回

| # | 场景 | 预期结果 |
|---|------|---------|
| 16 | 用户选 reject_with_suggestion | 返回 UserResponse(kind="reject_with_suggestion", rejection=RejectionWithSuggestion(sig, text)) |
| 17 | RejectionWithSuggestion 是 typed 结构 | 不是字符串，不是混入 error message |

### 队列并发

| # | 场景 | 预期结果 |
|---|------|---------|
| 18 | 同 session 并发两个 request | 第二个在 QueueManager 排队，等第一个完成 |
| 19 | 不同 session 并发 request | 互不影响，独立处理 |
| 20 | 同 session 前序 resolve 后，排队者正常执行 | 队列 FIFO 推进 |

---

## 四、Contract Specification（契约规约）

服务编排模块，不适用此章节（见 test-guide.md 第七节速查表）。

---

## 五、Integration Points（集成点测试）

| 集成点 | 测试类型 | 验证重点 |
|--------|---------|---------|
| AllowStore ↔ AppSettingsService（DB） | integration | key 格式 `permissions.user_local.<scope>.allow.<sig>` 精确匹配；`clear_skill_permissions` 的 LIKE 前缀删除覆盖范围 |
| ConfirmationDispatcher ↔ ConfirmationGateway | integration | 事件字段扩展向后兼容（旧字段不变 + 新字段存在）；resolve 能唤醒 wait |
| QueueManager ↔ SessionManager | unit（mock） | session_id / turn_id 正确传递；会话结束时 QueueManager 收到通知 |
| DecisionRecorder ↔ AllowStore + SessionAllowCache | unit（mock） | 按响应类型调正确的落地组件；always_persist 写 DB 失败时不调 AllowStore 之外的动作 |
| clear_skill_permissions ↔ skills 模块 | integration | skills 调 `clear_skill_permissions(name)` 后 DB 与 session 内存均清除 |

---

## 六、Verification Strategy（验证策略）

### 执行环境

- unit 测试：纯 Python，无需外部服务（mock DB/SSE）
- integration 测试：需要内存 SQLite（或真实 PG 连接），可选启动 SSE 测试客户端

### 测试组织

```
tests/unit/core/permission/
├── test_gateway.py                  # PermissionGateway 编排路径（mock 所有子组件）
├── test_allow_store.py              # AllowStore lookup/write/delete_by_skill（mock DB 或内存 SQLite）
├── test_session_cache.py            # SessionAllowCache add/get/clear/remove_by_skill
├── test_queue_manager.py            # QueueManager enqueue/cancel/cascade/non-blocking
├── test_dispatcher.py               # ConfirmationDispatcher 事件构造与字段完整性
└── test_recorder.py                 # DecisionRecorder 四种响应落地 + typed rejection

tests/integration/core/permission/
├── test_request_flow.py             # 完整 request() 流程：DB 命中/未命中 → 弹卡 → 等响应 → 落地
├── test_clear_skill_permissions.py  # 级联清理：DB 删除 + session 内存清除
└── test_fail_closed.py              # DB 不可达/SSE 断连/gateway 丢失均拒绝
```

### 关键测试模式

- **缓存命中短路**：先写 SessionAllowCache，再调 `request()` 断言不查 DB（验证 mock DB 未被调用）
- **DB 命中短路**：先写 AllowStore，再调 `request()` 断言不弹卡（验证 mock dispatcher 未被调用）
- **序列化 QueueManager**：用 asyncio.gather 同时发两个 request，断言第二个的 timestamp > 第一个的 resolve timestamp
- **Fail-closed 全覆盖**：每个取消/异常路径都断言返回 UserResponse.kind != "allow"
- **级联清理完整性**：install → allow → uninstall → 再次 request → 断言进入弹卡路径（旧许可已清除）
