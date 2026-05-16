# permission 模块 dfd-interface.md

本文档描述 `newbee_notebook/core/permission/` 模块的数据流与对外接口，说明数据如何进入模块、经何种处理、以何种形态输出。设计严格基于 [goals-duty.md](goals-duty.md) 与 [architecture.md](architecture.md)。

---

## 一、Context & Scope（上下文与范围）

permission 模块处于 agent_loop 工具调用链的**人机闭环节点**：当 policy 返回 `ASK` 决策时，agent_loop 调用 `PermissionGateway.request()` 完成"查已允许 → 弹卡等响应 → 落地许可"流程。permission 是 `permissions.*` DB 表的**唯一读写者**。

### 与外部模块的交互关系

| 方向 | 模块 | 角色 |
|------|------|------|
| 输入来源 | agent_loop | 调用方，传入 `PermissionRequest`（含 policy 生成的 capability_signature） |
| 输入来源 | 前端（经 SSE） | 用户对确认卡的响应 |
| 输入来源 | skills（级联清理） | 调 `clear_skill_permissions(name)` |
| 输入来源 | SessionManager | 提供 session_id、assistant_turn_id；会话结束触发 clear_session |
| 输出去向 | agent_loop | 返回 `UserResponse`（allow / deny / reject_with_suggestion） |
| 输出去向 | 前端（经 SSE） | 推确认卡事件 `ConfirmationRequestEvent` |
| 输出去向 | AppSettingsService（DB） | 写入 `permissions.*.allow.*` 永久许可记录 |
| 读/写 | AppSettingsService（DB） | 查询已存在的永久 allow 记录 |
| 不交互 | policy | permission 不主动调 policy，仅被 agent_loop 在 policy 返回 ASK 后调用 |

### 本文档范围

描述 permission 模块内部的完整数据流：从接收 `PermissionRequest` 到返回 `UserResponse`，含永久允许的 DB 读写路径、弹卡等待路径、队列取消路径、级联清理路径。不描述 agent_loop 如何决定调用 permission（那是 agent_loop 的职责），不描述前端如何渲染确认卡。

---

## 二、Data Flow Description（数据流描述）

permission 有三条核心数据流路径和三条取消/清理路径。

### 路径一：已允许命中（不弹卡）

```
agent_loop（收到 policy.ASK 后）
  │
  │  PermissionRequest(session_id, assistant_turn_id, tool_call_id,
  │                     capability_signature, tool_name, args_summary,
  │                     risk_level, skill_context, db_session)
  ▼
PermissionGateway.request()
  │
  ├─(1)─ SessionAllowCache.get(session_id, signature)
  │      命中 → 返回 UserResponse.allow(reason="session_allow")
  │
  ├─(2)─ AllowStore.lookup(user="local", scope=derive_scope(signature), sig=signature)
  │      DB 查询: SELECT value FROM app_settings
  │                WHERE key = "permissions.user_local.<scope>.allow.<sig>"
  │      命中 → 返回 UserResponse.allow(reason="permanent_allow")
  │
  └─ 均未命中 → 进入路径二
```

### 路径二：待确认（弹卡等响应）

```
（接路径一未命中）
  │
  ├─(3)─ QueueManager.enqueue(session_id, assistant_turn_id, tool_call_id)
  │      串行化：同一 session 同一时刻仅一个待确认
  │      若同 assistant_turn 前序已被 reject → 当前直接返回 reject（"前序被拒"）
  │
  ├─(4)─ ConfirmationDispatcher.dispatch(PermissionRequest)
  │      v1 复用 ConfirmationGateway（asyncio Event 原语）
  │      构造 ConfirmationRequestEvent，附加字段：
  │        capability_signature, response_options["once"|"always_session"|
  │        "always_persist"|"reject_with_suggestion"],
  │        risk_level, skill_name, content_hash
  │      推 SSE 到前端
  │
  ├─(5)─ 阻塞等待 ConfirmationGateway.wait(signature)
  │      用户在前端确认卡上选择响应类型
  │
  ├─(6)─ 前端 SSE 通道回传用户选择
  │      ConfirmationGateway.resolve(signature, user_choice)
  │
  ├─(7)─ DecisionRecorder.record(choice)
  │      ├─ "once"            → 不写任何记录
  │      ├─ "always_session"  → SessionAllowCache.add(session_id, signature)
  │      ├─ "always_persist"  → AllowStore.write(user="local", scope=..., sig=signature)
  │      │                      先写 DB 成功，再返回 allow（写入失败则返回 PersistenceFailure）
  │      └─ "reject_with_suggestion"
  │                           → 构造 RejectionWithSuggestion(signature, suggestion_text)
  │
  └─(8)─ 返回 UserResponse 给 agent_loop
```

### 路径三：级联清理（skill 卸载触发）

```
skills.SkillLifecycle.uninstall()
  │
  │  clear_skill_permissions(skill_name)
  ▼
PermissionGateway.clear_skill_permissions(name)
  │
  ├─ AllowStore.delete_by_skill(name)
  │   DB: DELETE FROM app_settings
  │        WHERE key LIKE "permissions.%.skill:<name>@%.allow.%"
  │
  └─ SessionAllowCache.remove_by_skill(name)
      遍历所有 session 内存，移除 scope 含 "skill:<name>@" 的条目
```

### 取消/清理路径

```
会话关闭 / SSE 断连
  → PermissionGateway.clear_session(session_id)
    → QueueManager.cancel_session(session_id)
      清该 session 所有队列项；所有 wait() 返回 "cancelled"
    → SessionAllowCache.clear(session_id)

generation abort
  → PermissionGateway.abort_turn(session_id, assistant_turn_id)
    → QueueManager.cancel_turn(session_id, turn_id)
      清该 turn 队列项；前序被拒的后续排队自动解除

backend 启动
  → PermissionGateway.reset_on_startup()
    → QueueManager.reset_all()     清所有进程内 pending
    → SessionAllowCache.reset_all() 清所有 session 内存
```

### 关键分支条件

| 条件 | 行为 |
|------|------|
| SessionAllowCache 命中 | 直接返回 allow，不查 DB、不弹卡 |
| AllowStore（DB）命中 | 直接返回 allow，不弹卡 |
| 同 turn 前序已被 reject | 返回拒绝，不入队 |
| always_persist 且 DB 写失败 | 返回 `PersistenceFailure`，不放行（fail-closed） |
| SSE 通道断开 | QueueManager 取消该 session 所有 pending，返回拒绝 |
| gateway 超时 / 丢失 | 返回拒绝（fail-closed） |

---

## 三、Interface Definition（接口定义）

### 3.1 对外暴露接口

#### PermissionGateway.request()

- **调用方**：agent_loop
- **语义**：处理一次 ASK——查已允许或弹卡等用户响应
- **输入**：`PermissionRequest`
  - `session_id: str`
  - `assistant_turn_id: str`
  - `tool_call_id: str`
  - `capability_signature: str` — policy 生成，格式 `{scope}:{tool}:{arg_hash8}`
  - `tool_name: str` — 用于前端展示
  - `args_summary: str` — 参数摘要（前端展示）
  - `risk_level: str` — 透传自 ToolDefinition
  - `skill_context: SkillContext | None` — skill 上下文（用于前端展示 skill 名）
  - `db_session` — FastAPI 依赖链注入
- **输出**：`UserResponse`
  - `kind: "allow" | "deny" | "reject_with_suggestion" | "cancelled"`
  - `reason: str`
  - `rejection: RejectionWithSuggestion | None` — typed 建议结构
- **同步/异步**：异步（DB 查询 + asyncio Event 等待）
- **错误**：超时/DB 故障/gateway 丢失均返回 `UserResponse(kind="deny", reason=...)`，不抛异常给调用方

#### PermissionGateway.clear_session()

- **调用方**：SessionManager（会话关闭）、SSE 断连处理
- **语义**：清理指定 session 的所有 pending + 内存许可
- **输入**：`session_id: str`
- **副作用**：QueueManager 取消队列 + SessionAllowCache 清空

#### PermissionGateway.abort_turn()

- **调用方**：agent_loop（generation abort）
- **语义**：取消指定 assistant turn 的所有 pending 确认
- **输入**：`session_id: str, assistant_turn_id: str`
- **副作用**：QueueManager 取消该 turn 队列

#### PermissionGateway.reset_on_startup()

- **调用方**：backend 启动逻辑
- **语义**：清空所有进程内 pending（fail-closed）
- **副作用**：QueueManager + SessionAllowCache 全量重置

#### PermissionGateway.clear_skill_permissions()

- **调用方**：skills.SkillLifecycle（skill 卸载）
- **语义**：级联删除指定 skill 的所有永久许可 + session 内存
- **输入**：`skill_name: str`
- **副作用**：AllowStore 删 DB 记录 + SessionAllowCache 删 session 内存

### 3.2 内部组件接口（供架构理解，外部不调用）

- `AllowStore.lookup(user, scope, sig) -> bool` — 查 DB 是否有永久 allow
- `AllowStore.write(user, scope, sig) -> None` — 写 DB 永久 allow
- `AllowStore.delete_by_skill(name) -> int` — 按 skill 名前缀删 DB
- `SessionAllowCache.get/add/clear(session_id, signature)` — 会话内存许可
- `QueueManager.enqueue/cancel_session/cancel_turn/reset_all` — 串行队列
- `ConfirmationDispatcher.dispatch/wait/resolve` — v1 复用 ConfirmationGateway
- `DecisionRecorder.record(choice) -> None` — 落地许可或构造 typed rejection

---

## 四、Data Ownership & Responsibility（数据归属与责任）

### 数据创建责任

| 数据 | 创建者 | 说明 |
|------|--------|------|
| `permissions.*.allow.*` DB 记录 | permission (AllowStore) | 唯一写入者 |
| `SessionAllowCache` 条目 | permission (SessionAllowCache) | 进程内存，session 关闭即失效 |
| `UserResponse` | permission | 唯一生产者 |
| `RejectionWithSuggestion` | permission (DecisionRecorder) | typed contract，不混入 error 字符串 |
| ConfirmationRequestEvent（SSE） | permission (ConfirmationDispatcher) | 扩展字段向后兼容 |

### 数据更新与销毁责任

| 数据 | 责任模块 | 说明 |
|------|----------|------|
| `permissions.*.allow.*` 删除 | permission (AllowStore) | skill 卸载时级联清除 |
| SessionAllowCache 清除 | permission | session 关闭/backend 重启/skill 卸载时清除 |
| QueueManager 队列清除 | permission | session 关闭/abort/backend 重启时清除 |

### 当前模块不负责的数据

| 数据 | 责任模块 | 说明 |
|------|----------|------|
| capability_signature 生成 | policy | permission 仅作字符串 key 使用 |
| Decision（ALLOW/ASK/DENY） | policy + agent_loop | permission 只处理 ASK 路径 |
| skill 目录管理 | skills | permission 仅在卸载时被通知清理许可 |
| UI 渲染 | 前端 permission-request-card | permission 只发结构化事件 |
| 工具执行 | agent_loop | permission 返回响应后不调 tool.execute() |

---

## 五、与其他模块 dfd-interface 的交叉引用

| 本文档描述的流向 | 对应模块文档 | 衔接点 |
|------------------|-------------|--------|
| PermissionRequest.capability_signature 来自 policy | [policy/dfd-interface.md](../policy/dfd-interface.md) | policy 生成 signature，经 agent_loop 传入 |
| clear_skill_permissions 由 skills 卸载触发 | [skills/dfd-interface.md](../skills/dfd-interface.md) | skills.D6 "级联卸载" |
| UserResponse 返回给 agent_loop | agent_loop | agent_loop 根据响应放行或拒绝工具 |
| ConfirmationRequestEvent 推给前端 | 前端 SSE 订阅 | 前端渲染确认卡 |

---

## 六、自检清单

- [x] 可以清楚说明每条数据从哪里来、到哪里去（agent_loop → request → cache/DB → SSE → 用户响应 → DecisionRecorder → UserResponse → agent_loop）
- [x] 所有接口都服务于明确的数据流（request / clear_session / abort_turn / reset_on_startup / clear_skill_permissions 各自对应一条路径）
- [x] 不存在数据责任不清或重复处理的风险（AllowStore 是 permissions.* 唯一读写者，session 内存与 DB 分层查询）
- [x] 与 goals-duty.md 的 Non-Duties 一致（不做决策、不渲染 UI、不生成 signature、不执行工具）
- [x] 与 architecture.md 的子组件划分一致（PermissionGateway 编排 AllowStore / SessionAllowCache / ConfirmationDispatcher / QueueManager / DecisionRecorder）
