# P10（回归验证）: UI 侧 Playwright 回归测试记录

---

## 1. 目的

在 `improve-2` 阶段完成 P1-P9 修复后，使用 Playwright MCP 对前端 UI 进行一轮端到端回归验证，重点确认：

1. 会话管理交互（新建会话、自动切换）
2. `Chat / Ask / Explain / Conclude` 四种模式的 UI 路径是否可用
3. 文档阅读器中的选区动作入口（`解释/总结`）是否正常
4. 修复后的 SSE 链路在 UI 层是否表现稳定（不再卡死/无响应）

---

## 2. 测试环境

### 2.1 运行环境

- 前端：`http://localhost:3000`
- 后端：`http://localhost:8000`
- Notebook：`db6080ce-bdd7-4362-b496-0d4523848ab4`（`test1`）
- LLM Provider：已切换（本轮为 `qwen` 配置）

### 2.2 测试方式

- 使用 Playwright MCP 进行真实页面操作与快照验证
- 配合浏览器 Network / Console 观察接口状态与前端错误

---

## 3. 回归范围与覆盖点

| 编号 | 验证项 | 对应问题/修复 | 结果 |
|------|--------|---------------|------|
| UI-1 | 新建会话后自动切换 | P4 | 通过 |
| UI-2 | `Ask` 模式发送与渲染 | P5/P8/P9（链路回归） | 通过 |
| UI-3 | 打开文档阅读器（来自引用来源） | P6/P7（阅读器回归） | 通过 |
| UI-4 | 文本选区后显示 `解释/总结` 按钮 | P2/P3/P7 | 通过 |
| UI-5 | `Explain` 侧栏生成并渲染结果 | P5/P9（SSE 长等待） | 通过 |
| UI-6 | `Conclude` 侧栏生成并渲染结果 | P5/P9（SSE 长等待） | 通过 |
| UI-7 | `Chat` 模式发送与渲染 | P5/P8/P9（链路回归） | 通过 |

---

## 4. 关键测试步骤与结果

### 4.1 新建会话自动切换（P4）

**步骤**

1. 打开 Notebook 页面
2. 点击 `+ 新建会话`
3. 观察会话下拉框当前选中项

**结果**

- 新建会话后会话下拉框立即切换到新会话（本轮验证到 `会话 13` 被选中）
- 未再出现“创建成功但仍停留在旧会话”的状态竞争问题

---

### 4.2 `Ask` 模式 UI 烟测

**步骤**

1. 在聊天面板切换到 `Ask`
2. 输入问题（示例：`1+1=? UI ask smoke`）
3. 点击发送

**结果**

- 用户消息与 AI 回复均正常渲染
- `引用来源` 区域正常显示
- 网络请求 `POST /api/v1/chat/notebooks/.../chat/stream` 返回 `200 OK`

---

### 4.3 文档阅读器 + 选区动作入口（P2/P3/P7）

**步骤**

1. 从 `Ask` 回复中的引用来源点击 `View`
2. 打开文档阅读器后，在目录区域（第 3 章）选中文本
3. 观察是否出现 `💡 解释`、`📝 总结` 动作按钮

**结果**

- 文档阅读器可正常打开并显示 Markdown 内容
- 选区后动作按钮正常出现
- 说明选区菜单触发链路在 UI 层可用（未出现按钮无法点/不出现的问题）

---

### 4.4 `Explain` 模式（侧栏生成结果）

**步骤**

1. 在阅读器中选中文字
2. 点击 `💡 解释`
3. 观察侧栏从“生成中”到结果渲染

**结果**

- 侧栏进入 `解释` 模式并显示选中文本摘要
- 先显示“正在生成内容.../生成中...”
- 随后成功渲染解释结果（包含标题、段落、列表）
- 未出现“前端一直拿不到响应”的 UI 卡死现象

---

### 4.5 `Conclude` 模式（侧栏生成结果）

**步骤**

1. 在阅读器中重新选中文字
2. 点击 `📝 总结`
3. 观察侧栏从“生成中”到结果渲染

**结果**

- 侧栏进入 `总结` 模式并显示选中文本摘要
- 最终成功渲染总结内容（本轮快照中已确认完整文本）
- 说明在当前 provider 配置下，`Conclude` UI 链路已通过回归验证

---

### 4.6 `Chat` 模式 UI 烟测（补测）

**步骤**

1. 从阅读器返回聊天面板
2. 切换模式为 `Chat`
3. 输入测试消息并发送（示例：`请用一句话确认 UI chat smoke`）

**结果**

- 用户消息与 AI 回复正常渲染
- 回复包含 `引用来源` 区域
- 网络请求正常返回 `200 OK`

---

## 5. Playwright 网络与控制台观察

### 5.1 Network（关键接口）

本轮 UI 回归过程中，以下关键请求均返回成功：

- `POST /api/v1/chat/notebooks/.../chat/stream` -> `200 OK`（多次）
- `POST /api/v1/notebooks/.../sessions` -> `201 Created`
- `GET /api/v1/sessions/{session_id}/messages` -> `200 OK`
- `GET /api/v1/documents/{document_id}/content?format=markdown` -> `200 OK`

### 5.2 Console（非阻塞项）

观察到以下前端控制台消息，但不影响本轮功能验证：

1. `favicon.ico` `404`（开发环境常见）
2. KaTeX strict warning（数学公式兼容性 warning）

---

## 6. 结论

### 6.1 回归结论

`improve-2` 阶段的前端 UI 侧关键链路在本轮 Playwright 回归中均通过：

- 会话创建与切换
- `Chat / Ask / Explain / Conclude` 四模式 UI 路径
- 阅读器打开、文本选区、动作按钮、侧栏结果渲染

### 6.2 阶段状态建议

在当前修复范围内，`improve-2` 可以视为 **完成（Done）**。

建议作为收尾动作保留以下内容（非阻塞）：

1. 后续 provider 切换时复用本回归矩阵进行快速验证
2. 将 `favicon.ico 404` 与 KaTeX warning 作为开发体验类事项单独管理（不计入 improve-2 阻塞项）

---

## 7. 关联文档

- `docs/frontend-v1/improve-2/04-sse-stream-cancellation-and-fallback.md`（P5）
- `docs/frontend-v1/improve-2/05-markdown-scroll-performance.md`（P6）
- `docs/frontend-v1/improve-2/06-text-selection-drag-scroll-jump.md`（P7）
- `docs/frontend-v1/improve-2/07-provider-switch-regression-and-chat-route-proxy.md`（P8 + P9）

