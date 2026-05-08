# policy-permission 前端模块 architecture.md

本文档描述 `frontend-v3/policy-permission` 前端模块的结构设计。设计严格服从 [goals-duty.md](goals-duty.md)：权限入口贴近发送框，审批卡通用化，policy 作用域清晰，sandbox 不暴露为用户操作台。

---

## 一、Architecture Overview（总体架构）

模块由六个子组件协作：

1. **Policy State Controller（权限状态控制器）**
   - 维护当前 notebook 与当前 session 的有效 policy。
   - 负责把用户选择转换为 chat 请求中的 `agent_policy`。
   - 负责在 `always_session` / `always_persist` 后更新 session / notebook 级状态。

2. **Policy Selector（发送框权限选择器）**
   - 位于 chat input toolbar 左侧，和 mode selector、source selector 同层。
   - 展示当前 policy，并通过 menu 允许用户切换 `默认权限` / `完全访问权限`。
   - UI 形态参考 Codex 式 compact policy pill：图标 + 短标签 + chevron。

3. **Permission Request Card（审批请求卡）**
   - 替换旧 `ConfirmationCard`。
   - 由 backend SSE `confirmation_request` 驱动，显示 agent 请求执行的工具行为。
   - 支持四个 response choice：once / always_session / always_persist / reject。

4. **Permission Event Adapter（SSE 事件适配层）**
   - 在 `useChatSession` 中把 backend SSE 事件转换为前端 `PendingPermissionRequest`。
   - 保留 `capability_signature`、`skill_name`、`content_hash`、`response_options` 等字段，供后续扩展。

5. **Policy API Adapter（API 契约适配层）**
   - 将旧 `approved: boolean` 确认接口升级为 `response` choice。
   - 将当前有效 `agent_policy` 注入 chat stream / chat once 请求。
   - 对 session / notebook policy 偏好进行读取和更新。

6. **Permission UI Styling（权限 UI 样式层）**
   - 复用现有 `chat.css`、`buttons.css`、`badges.css`、CSS variables。
   - 不引入新的 UI 库。
   - 将权限语义色限制在现有 `--bee-amber` / `--destructive` / muted tokens 范围内。

### 高层依赖关系

```text
ChatInput
  ├─► PolicySelector
  │     ├─ reads EffectivePolicyState
  │     └─ emits PolicyChangeIntent
  │
  └─► onSend(text, mode, sourceDocIds, agentPolicy)
        │
        └─► chatStream / chatOnce
              request.agent_policy := effective policy

SSE confirmation_request
  └─► Permission Event Adapter
        └─► ChatMessage.pendingPermission
              └─► MessageItem
                    └─► PermissionRequestCard
                          ├─ once              → confirm(response="once")
                          ├─ always_session    → confirm(response="always_session") + session policy yolo
                          ├─ always_persist    → confirm(response="always_persist") + notebook policy yolo
                          └─ reject            → confirm(response="reject")
```

---

## 二、Design Pattern & Rationale（设计模式与理由）

### 1. Scoped Policy State：按作用域建模，而不是按按钮建模

权限不是一个简单 boolean。它至少包含三层语义：

- 当前请求：`once`
- 当前 session：`always_session`
- 当前 notebook：`always_persist`

因此前端状态应围绕 `scope + policy` 组织，而不是围绕“按钮是否点过”组织。这样可以自然表达“session2 不继承 session1 的本会话授权”。

### 2. Menu Button over Segmented Control：菜单优于常驻分段控件

输入框已经包含 Agent / Ask、source selector、发送按钮。policy 是低频但关键操作，适合用 compact menu button：

- 默认状态占用很小空间。
- 点击后明确展示可选项。
- 当前选中项可用 check mark 表达。
- 视觉上更接近 Codex 权限选择体验。

### 3. Generic Permission Card：后端描述优先

旧 confirmation card 的核心问题是前端写死了 `create/update/delete/confirm` 与 `note/diagram/video` 的组合。

新版卡片应以 backend event 为事实来源：

- `description` 是主标题或主说明。
- `tool_name` 是工具身份。
- `args_summary` 是可检查的操作摘要。
- `response_options` 决定卡片展示哪些按钮。

前端只负责排版与安全默认文案，不继续扩散 skill-specific 规则。

### 4. Optimistic UI with API Reconciliation：点击后先反馈，再等待接口

用户点击 permission action 后，卡片应立即进入 resolving 状态，避免像按钮失灵。

如果 confirm API 失败：

- 卡片回到 pending 或显示错误状态。
- policy selector 不应保留未被后端接受的状态。

这个模式能兼顾交互速度与后端权威性。

### 5. CSS Token First：样式优先复用现有 token

该模块不是视觉重做，因此样式策略是：

- 背景：`--card`
- 边框：`--border`
- 普通文字：`--foreground`
- 次要文字：`--muted-foreground`
- 完全访问强调：`--bee-amber`
- 拒绝 / 危险：`--destructive`

不新增大面积渐变、不做重阴影、不创建新的卡片系统。

---

## 三、Module Structure & File Layout（模块结构与文件组织）

```text
frontend/src/
├ components/
│  └ chat/
│     ├ chat-input.tsx
│     │  扩展：接收 policy 状态；在 toolbar 渲染 PolicySelector
│     ├ chat-panel.tsx
│     │  扩展：向 ChatInput / MessageItem 透传 policy 与 permission callbacks
│     ├ message-item.tsx
│     │  扩展：渲染 PermissionRequestCard 与 collapsed inline tag
│     ├ permission-request-card.tsx
│     │  新增或替代 confirmation-card：通用审批卡
│     ├ permission-request-card.test.tsx
│     │  新增：四按钮 payload 与 UI 状态
│     ├ policy-selector.tsx
│     │  新增：compact policy pill + menu
│     └ policy-selector.test.tsx
│        新增：菜单打开、选中态、回调
├ lib/
│  ├ api/
│  │  ├ chat.ts
│  │  │  扩展：confirmChatAction 支持 response；chat request 支持 agent_policy
│  │  └ types.ts
│  │     扩展：SseEventConfirmation 与 ChatRequest policy 字段
│  └ hooks/
│     └ useChatSession.ts
│        扩展：policy state、permission event adapter、resolvePermission
├ stores/
│  └ chat-store.ts
│     扩展：PendingPermissionRequest / EffectivePolicyState 类型
├ lib/i18n/
│  └ strings.ts
│     新增：policyPermission.* 文案命名空间
└ styles/
   └ chat.css
      新增：policy selector、permission card、responsive actions
```

### 后端配套契约（不属于前端模块内部职责）

```text
newbee_notebook/api/models/requests.py
  ChatRequest 增加 agent_policy?: "default" | "yolo"

newbee_notebook/api/models/confirm_models.py
  已支持 response: "once" | "always_session" | "always_persist" | "reject"

Policy Preference API
  需要提供 session / notebook 级 policy 偏好的读取与更新
  具体 endpoint 名称可在实施计划阶段确定
```

---

## 四、Architectural Constraints & Trade-offs（约束与权衡）

### 1. 不引入 shadcn / Radix / Headless UI

**取舍**：放弃成熟 menu 组件库，沿用项目当前自写 popover 模式。

**理由**：项目当前 UI primitive 很少，`SourceSelector` 已有外部点击关闭、面板浮层、加载态等模式。为一个 policy menu 引入新库会增加样式和 bundle 对齐成本。

### 2. 不显示风险等级

**取舍**：放弃展示 `safe/moderate/dangerous` 的细粒度说明。

**理由**：用户当前核心诉求是 policy 选择和 permission 审批。风险等级一旦显示，就需要解释规则、颜色、含义和误判，这会显著扩大 UI 设计范围。

### 3. `自动审查` 暂缓

**取舍**：菜单当前只做 `默认权限` 与 `完全访问权限`。

**理由**：backend-v4 当前只有 `AgentPolicy.DEFAULT` 和 `AgentPolicy.YOLO`。`自动审查` 需要第三种后端 policy 语义，否则前端显示会制造虚假能力。

### 4. Permission Card 保持在消息流内

**取舍**：不做全局 modal，不把审批请求放在右侧面板。

**理由**：审批请求属于某次 agent 回复的上下文。放在消息流内，用户能直接看到“agent 说到哪一步触发了审批”。

### 5. `always_persist` 解释为 notebook 级完全访问

**取舍**：不沿用“仅某 capability signature 永久允许”的狭义解释。

**理由**：用户明确要求“当前 notebook 内所有 sessions 都让 agent 自行执行”。前端文案和状态模型应以 notebook scope 表达，后端需要同步支持该语义。

### 6. 手动切回默认权限必须覆盖自动授权状态

**取舍**：用户在 policy selector 中选择 `默认权限` 时，应清除当前可见作用域下的完全访问授权。

**理由**：用户把 policy selector 视为当前权限开关。如果 UI 显示默认但后端仍按 notebook yolo 执行，会破坏信任。

### 7. CSS 以现有 token 为边界

**取舍**：不新增完整权限主题色板，只增加少量语义 class。

**理由**：chat surface 已经稳定；新权限 UI 应像系统自然长出来的一部分，而不是另一个视觉体系。
