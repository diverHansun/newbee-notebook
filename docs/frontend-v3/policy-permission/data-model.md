# policy-permission 前端模块 data-model.md

本文档描述 `frontend-v3/policy-permission` 模块的核心概念。它不是 TypeScript 类型定义清单，而是用于统一前端、后端与后续实现讨论中的概念语言。

---

## 一、Core Concepts（核心概念）

### 1. Agent Policy（Agent 执行策略）

表示 agent 在后续工具调用中是否需要触发用户审批。

- `default`：默认权限。仍带 sandbox；读操作通常放行；敏感 bash、写入、数据库增删改等操作由后端 policy 判定是否 ASK。
- `yolo`：完全访问权限。仍带 sandbox；后端不再弹 permission 审批，agent 自行执行。

UI 文案中不显示 `yolo`，统一显示为 `完全访问权限`。

### 2. Policy Scope（权限作用域）

表示一次 policy 选择影响的范围。

- `request`：仅当前 permission request。
- `session`：仅当前 chat session。
- `notebook`：当前 notebook 下所有 sessions。

### 3. Effective Policy State（当前有效权限状态）

发送框展示的当前 policy。它不是单一值，而是由默认值、session override、notebook preference 共同推导。

关键要素：

- 当前有效 policy：`default` 或 `yolo`。
- 来源：default / session / notebook。
- 可清除范围：当用户切回默认权限时，应该清除哪个作用域的授权。

### 4. Permission Request（审批请求）

后端通过 SSE 发给前端的审批请求，表示 agent 想执行某个需要用户确认的操作。

关键要素：

- `request_id`：后端用于 resolve 的请求标识。
- `tool_name`：触发审批的工具名。
- `description`：给用户看的自然语言描述。
- `args_summary`：操作参数摘要。
- `capability_signature`：后端内部用于能力签名与记录。
- `response_options`：允许前端展示的响应选项。

### 5. Permission Response（审批响应）

用户对审批请求做出的选择。

- `once`：允许本次。
- `always_session`：本会话始终允许。
- `always_persist`：当前 notebook 永久允许。
- `reject`：拒绝。

### 6. Permission Card Status（审批卡状态）

用于控制卡片交互与动画。

- `pending`：等待用户选择。
- `resolving`：用户已点击，等待 API 返回。
- `confirmed`：请求已允许。
- `rejected`：请求已拒绝。
- `timeout`：请求超时。
- `error`：提交选择失败，需要允许用户重试。
- `collapsed`：已折叠为 inline tag。

---

## 二、Entity / Value Object 区分

### Entity

1. **Permission Request**
   - 有 `request_id`。
   - 有生命周期：pending → resolved / timeout / error。
   - 与一条 assistant message 绑定。

2. **Effective Policy State**
   - 与当前 notebook / session 绑定。
   - 会随用户切换 session、点击 permission card、手动调整 policy selector 而变化。

### Value Object

1. **Agent Policy**
   - 仅表达策略值，无独立生命周期。

2. **Policy Scope**
   - 仅表达作用域，无独立身份。

3. **Permission Response**
   - 仅表达一次用户选择。

---

## 三、Key Data Fields（关键数据字段）

### Effective Policy State

- `policy`：当前生效策略。
- `source`：策略来自 default、session 还是 notebook。
- `sessionId`：当 source 为 session 时，用于确认作用范围。
- `notebookId`：当 source 为 notebook 时，用于确认作用范围。
- `updatedAt`：用于避免慢请求覆盖新选择。

### Permission Request

- `requestId`：resolve API 必须携带。
- `toolName`：显示给用户并用于调试。
- `description`：卡片主文案。
- `argsSummary`：以 key-value 形式渲染。
- `responseOptions`：决定按钮可见性；若后端缺省，则使用四项默认集合。
- `riskLevel`：保留字段，本阶段不展示。
- `status`：控制卡片当前状态。

### Policy Change Intent

表示用户从 policy selector 触发的切换意图。

- `targetPolicy`：用户希望切到的策略。
- `targetScope`：本次切换写入 session 还是 notebook。
- `reason`：manual_selector / permission_always_session / permission_always_persist。

---

## 四、Lifecycle & Ownership（生命周期与归属）

1. **notebook 级 policy**
   - 创建：用户点击 `永久允许` 或在 selector 中对 notebook scope 选择完全访问。
   - 更新：用户在 selector 中切回默认权限。
   - 归属：后端应作为权威存储；前端只缓存展示。

2. **session 级 policy**
   - 创建：用户点击 `本会话始终允许` 或在 selector 中对当前 session 选择完全访问。
   - 更新：用户在 selector 中切回默认权限，或切换到另一个 session 后重新计算。
   - 归属：后端 session 状态为权威；前端在 `useChatSession` 中维护当前展示缓存。

3. **permission request**
   - 创建：SSE 收到 `confirmation_request`。
   - 更新：用户点击按钮、API 返回、超时计时器触发。
   - 销毁：消息折叠、session 切换、stream 结束清理。

4. **effective policy**
   - 创建：进入 notebook 或 session 时由后端偏好与默认值推导。
   - 更新：用户手动切换、permission card 选择、session 切换。
   - 归属：前端负责展示与请求携带；后端负责最终执行语义。
