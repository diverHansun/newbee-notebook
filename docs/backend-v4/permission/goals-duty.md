# permission 模块 goals-duty.md

本文档定义 `newbee_notebook/core/permission/` 模块的设计目标与职责边界。

---

## 一、模块定位

**一句话说明**：permission 模块是"敏感操作的人机闭环执行层 + 永久允许记录的唯一归属"——当 agent_loop 收到 policy 的 `ASK` 决策时，调用 permission 完成四件事：查已有允许→若有直接放行；若无，通过 SSE 推卡给前端；等用户响应并返回 `allow / deny(含建议)`；把"始终允许"的记录写 DB。policy 从不接触 DB，permission 是永久允许记录的**唯一读写者**。

**如果没有这个模块**：
- policy 返回 `ASK` 决策后无组件承接，工具会被直接执行（不安全）或永久阻塞
- "始终允许此 skill 此内容版本此命令"这种分级记忆无处归属
- 永久允许表没有单一事实源，policy 与 permission 双查 DB 会产生一致性风险
- 多并发工具调用会同时弹多张卡，用户体验混乱
- backend 重启时悬挂的 `wait()` 无人清理

---

## 二、Design Goals（设计目标）

### G1：单一职责

只负责"查已允许 / 询问用户 / 记录用户决定"。不做决策（policy 负责）、不渲染 UI（前端负责）、不执行工具（agent_loop 负责）。

### G2：永久允许的唯一事实源

permission 是 `permissions.*.allow.*` 表的**唯一读写者**。policy 完全不读 DB。任何"是否已经被允许过"的查询都经过 permission。

### G3：复用既有事件链路（v1）

v1 复用 [ConfirmationGateway](../../../newbee_notebook/core/engine/confirmation.py) 的 asyncio Event 原语与 SSE `ConfirmationRequestEvent` 推送机制（以向后兼容的方式扩展字段）。不引入新事件总线。v2 会把内置 skill（note/diagram/video）现有的 confirmation_required 迁移进 permission，届时 ConfirmationGateway 类作为 permission 内部组件存在，不再被外部直接引用。

### G4：分级记忆 + 内容版本绑定

支持四种用户响应粒度：
- **once**：仅本次放行
- **always_session**：本会话内同 signature 不再询问
- **always_persist**：跨会话，但**绑到 skill 内容哈希**——skill 更新或被替换后旧许可失效
- **reject_with_suggestion**：拒绝并附建议

capability_signature 由 policy 生成，permission 仅作字符串键使用。

### G5：并发/生命周期严格可定义

permission 队列以 `(session_id, assistant_turn_id, tool_call_id)` 为 key；同 `assistant_turn` 内前一个 ASK 被 reject 时，取消后续所有同 turn 的排队 ASK（避免基于失效 plan 的调用）。backend 重启、会话关闭、SSE 断连、generation abort 均触发"清队列 + 发 ExpiredEvent"。

### G6：Fail-closed

任何异常路径（gateway 丢失、超时、会话已结束、内容哈希对不上）默认**拒绝**并返回 typed rejection，不放行、不重试、不回退到"允许"。

### G7：预留多用户 scope

permanent allow key 加 `user_id` 前缀占位（v1 固定 `local`），便于未来升级到多用户部署时无缝扩展。单用户是当前默认假设。

### G8：拒绝建议是 typed contract

用户拒绝时可输入一句话建议，permission 返回给 agent_loop 的结构是 **typed** 的 `RejectionWithSuggestion`（而不是塞进 error 字符串），由 agent_loop 翻译成 mellow 可理解的 tool call metadata。

---

## 三、Duties（职责）

### D1：受理确认请求

提供 `request(req: PermissionRequest) -> UserResponse` 接口。`PermissionRequest` 字段：
- `session_id`
- `assistant_turn_id`
- `tool_call_id`
- `capability_signature`（policy 生成）
- `tool_name` / `args_summary` / `risk_level` / `skill_context`（用于前端展示）
- `db_session`（FastAPI 依赖链注入）

### D2：查已允许缓存（两层）

在弹卡前按顺序查：
1. 会话内存中的 `always_session` 集合
2. DB `permissions.user_<uid>.<scope>.allow.<sig>`（其中 scope 对 skill 调用含 `@<content_hash>`，对全局调用为 `global`）

命中则直接返回 `allow`，不发卡。

### D3：通过 SSE 推卡

构造扩展版 `ConfirmationRequestEvent`（新增 `capability_signature` / `response_options` / `risk_level` / `skill_name` / `content_hash` 字段；旧字段保持兼容，这是**向后兼容的协议演化**），推到当前会话的 SSE 流。

### D4：等待用户响应并 resolve

内部用 asyncio Event（v1 复用 ConfirmationGateway）等用户响应。响应有四种值（见 G4）。响应回来后 permission 按类型落地（D5），然后返回给调用方。

### D5：写入批准记录

- `always_session`：写会话内存
- `always_persist`：写 DB `app_settings` 表，key 形如 `permissions.user_<uid>.<scope>.allow.<sig>`，其中 `<scope>` 形如 `skill:my-skill@a1b2c3d4` 或 `global`
- `once` / `reject_*`：不写

### D6：队列与取消

同 session 的多个 ASK 按 `(session_id, assistant_turn_id, tool_call_id)` 排队，串行处理。前一个 reject 时取消同 assistant_turn 的所有后续排队请求（返回"前序被拒绝"的典型 rejection）。

### D7：清理钩子

暴露清理接口，在以下场景调用：
- `clear_session(session_id)`：会话关闭 / SSE 断连 / 用户刷页重连
- `abort_turn(session_id, assistant_turn_id)`：generation abort
- `reset_on_startup()`：backend 启动时清空所有进程内 pending（任何启动时仍 pending 的 wait 均 fail-closed）

### D8：拒绝建议 typed 返回

用户选择 `reject_with_suggestion` 时，返回 `RejectionWithSuggestion(signature, suggestion_text)`，agent_loop 负责把它翻译为 ToolCallResult.metadata，不能混入 error 字符串。

### D9：skill 卸载级联清理

暴露 `clear_skill_permissions(skill_name)` 接口，在 skill 卸载时被 skills 模块调用——删除该 skill 在 DB 中的所有 `permissions.user_*.skill:<name>@*.allow.*` 记录 + 清空相关 session 内存。

---

## 四、Non-Duties（非职责）

### N1：不做决策

`ALLOW / DENY / ASK` 由 policy 计算。permission 仅在 agent_loop 收到 policy 的 `ASK` 后被调用。

### N2：不渲染 UI

确认卡样式、按钮文案、动画由 [confirmation-card.tsx](../../../frontend/src/components/chat/confirmation-card.tsx) 负责。permission 只发结构化事件。

### N3：不定义工具风险等级

`risk_level` 由 ToolDefinition 自身声明，permission 透传给前端展示，不修改、不重新分类。

### N4：不管理工作模式

agent/ask 模式、agent policy 档位由 policy 维护。permission 不读、不切。

### N5：不实现用户级超时

permission 不自己实现"用户 N 秒没响应"。agent_loop 的 180s 兜底仍有效。但 permission 自己负责**系统级取消**（会话关闭、generation abort、进程重启），与用户级超时不冲突。

### N6：不直接执行工具

收到响应后只 resolve 并返回给 agent_loop，不调用 tool.execute()。

### N7：不感知 skill 内部结构

permission 不读 SKILL.md、不解析 scripts/。它只收到 `skill_name + content_hash` 字符串用于拼 scope。

### N8：不持久化"本会话允许"

`always_session` 只在内存，进程重启丢失（fail-closed）。

### N9：不生成 capability_signature

签名由 policy 生成。permission 仅作字符串 key 使用，不解析、不重写。

### N10：v1 不替代内置 skill confirmation

内置 skill（note/diagram/video）的 `confirmation_required` 在 v1 保留原 ConfirmationGateway 路径不动，以避免炸掉现有流程。v2 会统一迁入 permission（届时 ConfirmationGateway 变为 permission 的内部实现细节）。

---

## 五、设计约束与假设

### 约束

1. **v1 扩展 ConfirmationGateway**：不重写，不立刻替换内置 skill 的旧路径（降低风险）
2. **DB 表复用**：永久白名单写入既有 `app_settings`，不新增表；key 格式 `permissions.user_<uid>.<scope>.allow.<sig>`
3. **`app_settings.key` 已是主键**：查询是 O(log n) 索引命中，满足"每次 decide 一次 DB 读"的性能要求
4. **串行处理**：同一会话同一时刻仅一个待确认（继承 agent_loop 既有行为，扩展为带 turn_id 的取消语义）
5. **签名由 policy 给**：permission 不生成签名，避免与 policy 重复
6. **user_id v1 固定 `local`**：多用户部署需额外设计（v2）

### 假设

1. policy 模块调用前已完成所有决策计算，传入的 signature 是规范化的
2. agent_loop 在收到 `ASK` 后负责调 permission、处理返回值
3. 前端订阅 SSE 流并识别新增字段（旧字段保持兼容）
4. SessionManager 提供 session_id、assistant_turn_id；skills 模块在 skill 卸载时调 D9
5. backend 进程重启视作"所有 session 失效"，启动时一次性清空进程内 pending

---

## 六、与其他模块的关系

| 模块 | 关系 | 说明 |
|------|------|------|
| policy | 上游 | policy 仅返回 `ASK`，agent_loop 据此调 permission |
| agent_loop | 调用方 | 调 `request()`；收到响应后放行/拒绝；生命周期事件（abort/close/startup）触发 permission 清理 |
| skills | 双向 | skills 向 policy 提供 skill_context + content_hash；skills 卸载时调 `clear_skill_permissions` |
| sandbox | 不直接 | permission 不感知执行层 |
| ToolRegistry | 被依赖（间接） | 通过 policy 传入 risk_level / tool_name / args_summary 用于展示 |
| ConfirmationGateway（v1） | 内部复用 | v1 作为 permission 的 wait/resolve 原语；v2 并入 permission |
| SessionManager | 被依赖 | 提供 session_id 与 assistant_turn_id；会话结束触发 clear_session |
| AppSettingsService | 依赖 | 读写 `permissions.user_*.<scope>.allow.<sig>` key |
| 前端 confirmation-card | 被依赖 | 订阅 SSE 事件；新增 variant 处理四种响应 + skill 内容指纹展示 |

---

## 七、文档自检

- [x] 可以用一句话说明模块存在的意义（人机闭环 + 永久允许唯一归属）
- [x] 可以清楚回答"不该做什么"（决策、UI、模式、签名生成、工具执行均不做）
- [x] 与 policy（decide 纯函数）、skills（内容哈希）、sandbox（执行隔离）边界清晰
- [x] 所有职责可测试（D1~D7 可集成测；D9 单测）
- [x] Fail-closed 语义覆盖 backend 重启 / 会话关闭 / SSE 断连 / generation abort
- [x] 内容哈希绑定永久许可，防止 skill 更新后的许可继承攻击
- [x] 预留多用户 scope，不阻塞未来演进
