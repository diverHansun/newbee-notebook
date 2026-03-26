# ConfirmationCard 优化 - 实施计划

## 实施顺序

后端先行, 前端跟进。每一步完成后验证无回归。

---

## 第 1 步: 后端 - 数据结构与事件扩展

### 1.1 新增 ConfirmationMeta (contracts.py)

在 `SkillManifest` 前新增 `ConfirmationMeta` 数据类, 并在 `SkillManifest` 上新增 `confirmation_meta` 字段。

文件: `newbee_notebook/core/skills/contracts.py`

### 1.2 扩展 ConfirmationRequestEvent (stream_events.py)

新增 `action_type` 和 `target_type` 字段, 带默认值保证向后兼容。

文件: `newbee_notebook/core/engine/stream_events.py`

### 1.3 AgentLoop 传递 confirmation_meta (agent_loop.py)

- `__init__` 新增 `confirmation_meta` 参数
- 两处 `ConfirmationRequestEvent` 生成代码中, 从 `_confirmation_meta` 查找并填充新字段

文件: `newbee_notebook/core/engine/agent_loop.py`

### 1.4 数据流传递 (session_manager.py, chat_service.py)

- `_build_loop` 和 `chat_stream` 新增 `confirmation_meta` 参数
- `_resolve_skill_runtime` 返回值新增 `confirmation_meta`
- `chat_service.py` 中 `ConfirmationRequestEvent` 的手动序列化新增 `action_type` 和 `target_type`

文件: `newbee_notebook/core/session/session_manager.py`, `newbee_notebook/application/services/chat_service.py`

### 1.5 注册 confirmation_meta (note/diagram provider)

在各 skill provider 的 `build_manifest` 中传入 `confirmation_meta` 字典。

文件: `newbee_notebook/skills/note/provider.py`, `newbee_notebook/skills/diagram/provider.py`

---

## 第 2 步: 前端 - 类型与状态

### 2.1 SSE 事件类型扩展 (types.ts)

`SseEventConfirmation` 新增 `action_type` 和 `target_type` 字段。

### 2.2 PendingConfirmation 类型变更 (chat-store.ts)

新增 `actionType`, `targetType`, `resolvedFrom` 字段; `status` 新增 `"collapsed"` 值。

### 2.3 状态流转 (useChatSession.ts)

- `trackPendingConfirmation`: 从 SSE 事件中提取新字段
- `resolveConfirmation`: 增加 1.5s 延时折叠逻辑
- timeout 回调: 增加 1.5s 延时折叠逻辑

---

## 第 3 步: 前端 - i18n 与组件

### 3.1 i18n 文案 (strings.ts)

新增 `confirmation.actionTitle` 嵌套结构和 `confirmDelete` 按钮文案。

### 3.2 ConfirmationCard 重构 (confirmation-card.tsx)

- 标题使用 `confirmationTitle()` 函数
- 隐藏 requestId 和倒计时
- 根据 actionType 切换确认按钮样式
- 根据 status 切换 CSS 动画类
- 新增 `ConfirmationInlineTag` 组件

### 3.3 渲染逻辑 (message-item.tsx)

根据 `status === "collapsed"` 切换渲染 `ConfirmationCard` 或 `ConfirmationInlineTag`。

---

## 第 4 步: 前端 - CSS

### 4.1 动画与样式 (chat.css)

- `.confirmation-card--pending` / `.confirmation-card--resolving` 状态类
- `@keyframes confirmation-fade-out` 动画
- `data-action-type="delete"` 危险操作样式
- `.confirmation-inline-tag` 内联标签样式

---

## 第 5 步: 验证

### 5.1 TypeScript 编译检查

`npx tsc --noEmit`

### 5.2 Playwright E2E 测试

在 http://localhost:3000/notebooks/db6080ce-bdd7-4362-b496-0d4523848ab4 上:
- 使用 /diagram 命令触发确认卡片, 验证:
  - 标题显示中文 (如 "确认图表类型")
  - requestId 不可见
  - 确认后卡片 fade out 并折叠为内联标签
- 使用 /note 命令触发 delete_note 确认, 验证:
  - 红色边框和 "确认删除" 按钮
  - 拒绝后卡片 fade out 并显示 "已拒绝" 内联标签
