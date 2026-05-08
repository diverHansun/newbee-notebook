# policy-permission 前端模块 test.md

本文档说明 `frontend-v3/policy-permission` 模块的测试策略。测试目标是验证权限 UI、policy 作用域和后端 API 契约在真实协作路径中可信。

---

## 一、Module Test Profile（模块测试档案）

- 模块原型：桥接 / 适配模块 + 服务编排模块
- 主要测试类型：component test、hook unit test、API contract test、少量 browser smoke
- Mock 边界：
  - 后端 HTTP / SSE 使用 mock。
  - React 组件使用真实渲染。
  - 不 mock policy selector 内部 UI 状态。
  - 不运行真实 Docker sandbox。
- 测试归属目录：
  - `frontend/src/components/chat/*.test.tsx`
  - `frontend/src/lib/hooks/useChatSession.test.tsx`
  - 如新增 API contract helper，可放在 `frontend/src/lib/api/*.test.ts`

---

## 二、Test Scope（测试范围）

覆盖：

- policy selector 展示当前 policy。
- policy selector 切换默认 / 完全访问。
- Permission Request Card 四个按钮的 payload。
- `always_session` 只影响当前 session。
- `always_persist` 影响当前 notebook 下所有 sessions。
- 手动切回默认权限后，后续请求重新使用 `agent_policy: "default"`。
- chat stream / chat once 请求携带当前 `agent_policy`。
- SSE `confirmation_request` 能转换为 pending permission request。
- confirm API 失败时 UI 可恢复。

不覆盖：

- 后端 policy decision 是否正确。
- Docker sandbox 是否正确执行。
- bash 命令真实执行。
- notes / diagram / videos 的业务 CRUD 正确性。
- 风险等级规则。

---

## 三、Critical Scenarios（关键场景）

### 正常路径

1. **默认权限发送消息**
   - Given 当前 policy 为默认权限。
   - When 用户发送消息。
   - Then chat request body 包含 `agent_policy: "default"`。

2. **手动切到完全访问**
   - Given 用户打开 policy menu。
   - When 选择 `完全访问权限`。
   - Then selector 显示完全访问，并且下一次请求包含 `agent_policy: "yolo"`。

3. **允许本次**
   - Given 收到 permission request。
   - When 用户点击 `允许本次`。
   - Then confirm API body 为 `{ request_id, response: "once" }`。
   - And selector 不切到完全访问。

4. **本会话始终允许**
   - Given 当前 session 为 session1。
   - When 用户点击 `本会话始终允许`。
   - Then confirm API body 为 `{ request_id, response: "always_session" }`。
   - And session1 effective policy 为 `yolo`。
   - And 切换到 session2 后 effective policy 不继承 session1 授权。

5. **永久允许**
   - Given 当前 notebook 为 notebook1。
   - When 用户点击 `永久允许`。
   - Then confirm API body 为 `{ request_id, response: "always_persist" }`。
   - And notebook1 下新建或切换 sessions 时 effective policy 为 `yolo`。

6. **拒绝**
   - Given 收到 permission request。
   - When 用户点击 `拒绝`。
   - Then confirm API body 为 `{ request_id, response: "reject" }`。
   - And selector 不改变。

### 异常路径

1. **confirm API 失败**
   - 卡片从 resolving 回到 error。
   - selector 不更新到未确认状态。
   - 用户可以重试。

2. **policy preference 更新失败**
   - selector 回滚到旧状态。
   - 后续请求不使用失败的 policy。

3. **SSE 字段不完整**
   - 缺少 `response_options` 时展示默认四按钮。
   - 缺少 `risk_level` 时 UI 不受影响。

4. **permission timeout**
   - 卡片显示 timeout/collapsed。
   - selector 不改变。

---

## 四、Contract Specification（契约规约）

### Chat Request

- 请求体必须允许 `agent_policy?: "default" | "yolo"`。
- 缺省时后端按 `default` 处理。
- 前端发送时应显式携带当前 effective policy。

### Confirmation Request SSE

前端必须接受以下基础字段：

- `type: "confirmation_request"`
- `request_id`
- `tool_name`
- `args_summary`
- `description`

前端应兼容以下扩展字段：

- `action_type`
- `target_type`
- `capability_signature`
- `risk_level`
- `skill_name`
- `content_hash`
- `response_options`

### Confirm Action

请求体：

```json
{
  "request_id": "req-1",
  "response": "once"
}
```

`response` 可选值：

- `once`
- `always_session`
- `always_persist`
- `reject`

成功响应：

```json
{
  "status": "resolved"
}
```

### Policy Preference

该契约需在实施计划阶段补齐 endpoint 名称，但测试应覆盖语义：

- 读取当前 notebook / session effective policy。
- 更新 session policy。
- 更新 notebook policy。
- 清除 session / notebook 的完全访问授权。

---

## 五、Integration Points（集成点测试）

1. **与 `useChatSession` 集成**
   - SSE event 到 message pending permission 的转换。
   - resolve permission 后的消息状态更新。
   - session 切换后的 policy 重新计算。

2. **与 `ChatInput` 集成**
   - policy selector 位于 toolbar。
   - stream 中禁用或限制切换行为。
   - 发送消息时携带 policy。

3. **与 `MessageItem` 集成**
   - assistant message 下展示 Permission Request Card。
   - resolved 后折叠 inline tag。

4. **与 i18n 集成**
   - 中文文案完整。
   - 英文文案可回退但不缺 key。

---

## 六、Verification Strategy（验证策略）

1. **组件测试**
   - 使用 Testing Library 渲染 `PolicySelector` 与 `PermissionRequestCard`。
   - 断言按钮文案、选中态、回调 payload、错误状态。

2. **hook 测试**
   - 扩展 `useChatSession.test.tsx`。
   - mock chat stream 与 confirm API。
   - 验证 policy 作用域与 SSE 转换。

3. **类型检查**
   - 运行 `pnpm typecheck`。
   - 确认旧 `approved: boolean` 调用点全部迁移。

4. **前端单元测试**
   - 运行 `pnpm test` 或目标测试文件。
   - 重点覆盖 card 与 selector。

5. **浏览器 smoke**
   - 启动 frontend dev server。
   - 在 chat panel 中手动检查：
     - policy menu 打开/关闭。
     - 长文案不溢出。
     - permission card 在桌面与窄屏下按钮不重叠。
     - full access amber 强调不破坏暗色模式。

6. **后端联调 smoke**
   - 启动 FastAPI。
   - 用 mock 或真实 agent 触发 `confirmation_request`。
   - 点击四个按钮，确认后端收到对应 `response`。
   - 验证 session / notebook 作用域符合设计。
