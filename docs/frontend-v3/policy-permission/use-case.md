# policy-permission 前端模块 use-case.md

本文档描述 `frontend-v3/policy-permission` 模块的关键业务动作。它补足目标、架构与数据流之间的执行语义，但不展开到实现级代码。

---

## 一、Use Case Overview（用例概览）

本模块包含四个关键 use case：

1. **Select Chat Policy**：用户在发送框下方选择当前权限策略。
2. **Send Message with Policy**：发送消息时把当前有效 policy 传给后端。
3. **Resolve Permission Request**：用户处理 agent 发出的 permission request。
4. **Recover from Permission UI Failure**：确认接口失败或超时时保持 UI 可恢复。

---

## 二、Main Flow Description（主流程描述）

### Use Case 1：Select Chat Policy

1. 用户点击发送框下方的 policy selector。
2. 前端展示 menu，包含：
   - `默认权限`
   - `完全访问权限`
3. 用户选择目标项。
4. 前端根据当前 effective policy source 判断更新作用域。
5. 前端调用 Policy Preference API。
6. API 成功后更新 selector 展示。

主结果：

- 用户能在发送下一条消息前明确当前权限。
- policy 状态与后端后续执行策略一致。

### Use Case 2：Send Message with Policy

1. 用户在 chat input 输入消息。
2. 用户点击发送。
3. 前端读取当前 effective policy。
4. chat request 携带 `agent_policy`。
5. 后端 agent loop 按该策略决定工具是否直接执行或触发 permission request。

主结果：

- UI 中看到的 policy 与本次 agent 执行策略一致。

### Use Case 3：Resolve Permission Request

1. 后端通过 SSE 发送 `confirmation_request`。
2. 前端在当前 assistant message 下渲染 Permission Request Card。
3. 用户选择：
   - `允许本次`
   - `本会话始终允许`
   - `永久允许`
   - `拒绝`
4. 前端调用 Confirm API。
5. API 成功后，卡片进入 resolved/collapsed。
6. 若选择的是 session/notebook 级允许，前端同步更新 policy selector。

主结果：

- 用户的选择既 resolve 当前请求，也按作用域影响后续请求。

### Use Case 4：Recover from Permission UI Failure

1. 用户点击 permission card 按钮。
2. Confirm API 请求失败或超时。
3. 前端停止 resolving 状态，显示错误反馈。
4. 如果 policy 状态尚未被后端确认，则回滚 selector。
5. 用户可以重试或拒绝。

主结果：

- 权限状态不会因为网络失败而出现“前端显示完全访问、后端仍在等待”的不一致。

---

## 三、Responsibility Boundaries（责任边界）

### 前端负责

- 展示当前 policy。
- 接收用户 policy 切换意图。
- 发送 chat request 时携带当前 policy。
- 渲染 permission request。
- 把用户按钮选择转换为 confirm API payload。
- 在 API 成功后同步 UI 状态。

### 后端负责

- 维护最终 policy / permission 判定。
- 决定是否需要 ASK。
- 持有 pending request 与 resolve 状态。
- 执行工具与 sandbox 约束。
- 维护 session / notebook policy preference 的权威数据。

### 不属于本模块负责

- bash 命令执行。
- 文件系统读写。
- sandbox 容器生命周期。
- skill 内部 CRUD 逻辑。
- 风险等级解释与审查策略建模。

---

## 四、Failure & Decision Points（失败点与决策点）

### 1. Confirm API 失败

预期行为：

- Permission card 显示 error 状态。
- 不更新 policy selector。
- 允许用户重试或拒绝。

### 2. Policy Preference API 更新失败

预期行为：

- selector 回到更新前状态。
- 展示简短错误反馈。
- 当前 chat request 不应使用未确认的新 policy。

### 3. SSE confirmation request 缺少扩展字段

预期行为：

- 只依赖 `request_id`、`tool_name`、`description`、`args_summary` 渲染基础卡片。
- `response_options` 缺失时使用四项默认按钮。

### 4. 用户切换 session

预期行为：

- session 级完全访问不迁移。
- notebook 级完全访问继续生效。
- pending card 仍归属于原消息，不应出现在新 session。

### 5. 用户手动切回默认权限

预期行为：

- 若当前完全访问来自 session，则清除 session 授权。
- 若当前完全访问来自 notebook，则清除 notebook 持久授权。
- 后续敏感操作重新触发 permission 审批。

### 6. Permission request 超时

预期行为：

- 卡片显示 timeout 并折叠。
- 不改变 policy selector。
- 后端继续按 timeout 处理当前工具调用。
