# policy-permission 前端模块 dfd-interface.md

本文档描述 `frontend-v3/policy-permission` 模块的数据流与接口边界。重点是说明数据从哪里来、经过前端如何转换、最终如何影响后端 agent 执行策略。

---

## 一、Context & Scope（上下文与范围）

本模块位于前端 chat main panel 内，主要与以下外部模块交互：

1. **Chat API**
   - 发送 chat once / stream 请求。
   - 请求中携带当前有效 `agent_policy`。

2. **Chat SSE Stream**
   - 接收 `confirmation_request` 事件。
   - 驱动消息流内的 Permission Request Card。

3. **Confirm API**
   - 提交用户对 permission request 的选择。
   - 从旧 `approved` 布尔值升级为 `response` choice。

4. **Policy Preference API**
   - 读取当前 notebook / session 的有效 policy。
   - 更新 session 级或 notebook 级 policy 偏好。

5. **Chat Store / useChatSession**
   - 保存当前消息、pending permission request、policy selector 展示状态。

本文档只描述 frontend-v3 权限 UI 与 API 交互，不描述后端 policy decision 的内部实现。

---

## 二、Data Flow Description（数据流描述）

### Flow 1：进入 notebook / session 后计算当前 policy

1. 用户进入某个 notebook。
2. 前端根据当前 `notebook_id` 与 `session_id` 请求 policy preference。
3. 后端返回 notebook policy、session policy 或 effective policy。
4. 前端生成 `EffectivePolicyState`。
5. `PolicySelector` 显示当前状态：
   - 默认权限
   - 完全访问权限
   - 可选显示来源提示：当前会话 / 当前笔记本

### Flow 2：用户通过 selector 手动切换 policy

1. 用户点击发送框下方的 policy button。
2. 前端打开 policy menu。
3. 用户选择 `默认权限` 或 `完全访问权限`。
4. 前端生成 `PolicyChangeIntent`。
5. 前端调用 Policy Preference API 更新对应作用域。
6. API 成功后，前端更新 `EffectivePolicyState`。
7. 后续 chat request 携带新的 `agent_policy`。

切换规则：

- 若当前完全访问来自 session，切回默认权限时清除当前 session override。
- 若当前完全访问来自 notebook，切回默认权限时清除当前 notebook 持久授权。
- 若当前无明确来源，手动切换只影响当前 session。

### Flow 3：发送消息时传递 agent policy

1. 用户输入消息并点击发送。
2. `ChatInput` 把当前 `EffectivePolicyState.policy` 传给上层。
3. `useChatSession` 调用 chat stream / chat once。
4. API request body 携带 `agent_policy`：
   - `default` → 后端按默认 policy decision 执行。
   - `yolo` → 后端按完全访问策略执行，但仍使用 sandbox。
5. 后端在工具调用阶段决定是否直接执行或发出 permission request。

### Flow 4：后端触发 permission request

1. 后端在 agent 工具调用前判定需要 ASK。
2. SSE 发送 `confirmation_request`。
3. 前端 `Permission Event Adapter` 将事件转换为 `PendingPermissionRequest`。
4. 对应 assistant message 渲染 Permission Request Card。
5. 用户选择四个按钮之一。

### Flow 5：用户点击 `允许本次`

1. 前端调用 Confirm API，body 为 `{ request_id, response: "once" }`。
2. 卡片进入 resolving。
3. API 成功后，卡片显示已允许并折叠。
4. policy selector 不发生变化。

### Flow 6：用户点击 `本会话始终允许`

1. 前端调用 Confirm API，body 为 `{ request_id, response: "always_session" }`。
2. API 成功后，前端把当前 session policy 更新为 `yolo`。
3. policy selector 显示 `完全访问权限`，来源为当前 session。
4. 当前 session 后续请求携带 `agent_policy: "yolo"`。
5. 切换到 session2 后，该授权不生效。

### Flow 7：用户点击 `永久允许`

1. 前端调用 Confirm API，body 为 `{ request_id, response: "always_persist" }`。
2. API 成功后，前端把当前 notebook policy 更新为 `yolo`。
3. 当前 notebook 下所有 sessions 的 effective policy 变为 `yolo`。
4. 用户之后可通过 policy selector 切回默认权限。

### Flow 8：用户点击 `拒绝`

1. 前端调用 Confirm API，body 为 `{ request_id, response: "reject" }`。
2. 卡片进入 resolving。
3. API 成功后，卡片显示已拒绝并折叠。
4. policy selector 不发生变化。

---

## 三、Interface Definition（接口定义）

### 1. Chat Request Interface

语义：向后端发送一次 chat 请求，并携带当前有效 agent policy。

输入：

- 用户消息
- 当前 session
- 当前 mode
- 当前 source documents
- 当前 `agent_policy`

输出：

- 非流式响应，或 SSE stream。

同步 / 异步：

- chat once 为异步 HTTP。
- chat stream 为异步 SSE。

### 2. Confirmation Request SSE Interface

语义：后端请求用户审批一次 agent tool execution。

输入：

- SSE event `type: "confirmation_request"`。

输出：

- 前端创建 pending permission request 并渲染卡片。

稳定字段：

- `request_id`
- `tool_name`
- `args_summary`
- `description`
- `response_options`

扩展字段：

- `action_type`
- `target_type`
- `capability_signature`
- `risk_level`
- `skill_name`
- `content_hash`

### 3. Confirm Action Interface

语义：提交用户对 permission request 的选择。

输入：

- `request_id`
- `response: "once" | "always_session" | "always_persist" | "reject"`
- 可选 `suggestion`

输出：

- `{ status: "resolved" }`

错误：

- request 不存在：显示卡片错误状态，并允许用户重试或折叠。
- 网络失败：不更新 policy selector，卡片显示失败。

### 4. Policy Preference Interface

语义：读取或更新 session / notebook 的 policy preference。

读取输入：

- `notebook_id`
- 可选 `session_id`

读取输出：

- notebook policy preference
- session policy preference
- effective policy
- policy source

更新输入：

- `scope: "session" | "notebook"`
- `policy: "default" | "yolo"`
- `notebook_id`
- 当 scope 为 session 时包含 `session_id`

更新输出：

- 更新后的 effective policy。

---

## 四、Data Ownership & Responsibility（数据归属与责任）

1. **后端拥有最终权限执行权**
   - 前端传递 `agent_policy`，但后端必须自行判定是否允许。
   - 前端不能作为安全边界。

2. **后端拥有 policy preference 的权威状态**
   - session / notebook 级 policy 应由后端持久化或至少在后端 session registry 中维护。
   - 前端可缓存，但不能与后端长期不一致。

3. **前端拥有 UI 临时状态**
   - menu open/close、卡片 resolving/error/collapsed、inline tag 等只属于前端。

4. **permission request 生命周期由后端发起，前端驱动 resolve**
   - request 创建来自后端 SSE。
   - request resolve 由用户点击前端按钮后提交给后端。

5. **chat message 仍是审批卡的展示容器**
   - Permission Request Card 归属于触发它的 assistant message。
   - session 切换或消息清理时，前端应清理对应 pending UI 状态。
