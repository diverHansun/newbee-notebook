# ConfirmationCard 优化设计 - 第一轮

## 背景

当前 ConfirmationCard 存在以下问题:

1. 卡片在确认/拒绝/超时后永久留存, 按钮消失但卡片本体占据空间
2. 展示 requestId、原始 tool_name 等开发者信息, 普通用户无法理解
3. description 由后端英文硬编码 (`"Agent requested to run {tool_name}"`), 无国际化
4. 状态切换无过渡动画
5. 所有操作类型 (创建/更新/删除) 样式一致, 危险操作无视觉警示
6. 组件与 diagram skill 耦合, 缺乏通用化设计

## 设计目标

- 卡片在确认/拒绝后短暂显示状态 (1.5 秒), 然后自动折叠为内联标签
- 展示人类可读描述 + 关键参数摘要, 隐藏技术字段
- 后端发送 `action_type` + `target_type` 结构化信息, 前端拼装本地化文案
- 删除类操作使用红色/警告色视觉区分
- 组件通用化, 支持 note / diagram / document 等多种场景

## 核心方案

采用"状态驱动渐变"方案, 卡片生命周期由 `pendingConfirmation.status` 驱动:

```
pending --> confirmed/rejected/timeout --> (1.5s) --> collapsed
```

- `pending`: 完整卡片, 可交互
- `confirmed/rejected/timeout`: 显示结果 badge, CSS fade out 动画
- `collapsed`: 渲染为内联小标签, 不可逆

## 文档索引

| 文档 | 内容 |
|------|------|
| [backend-changes.md](backend-changes.md) | 后端结构化事件改造 |
| [frontend-state.md](frontend-state.md) | 前端类型定义与状态管理 |
| [component-design.md](component-design.md) | 组件重设计与 i18n 策略 |
| [css-style.md](css-style.md) | CSS 动画与样式规范 |

## 影响范围

### 后端

- `newbee_notebook/core/skills/contracts.py` -- SkillDefinition 新增 confirmation_meta
- `newbee_notebook/core/engine/agent_loop.py` -- ConfirmationRequestEvent 新增字段
- `newbee_notebook/skills/note/provider.py` -- 注册 note skill 的 confirmation_meta
- `newbee_notebook/skills/diagram/provider.py` -- 注册 diagram skill 的 confirmation_meta

### 前端

- `frontend/src/lib/api/types.ts` -- SseEventConfirmation 类型扩展
- `frontend/src/stores/chat-store.ts` -- PendingConfirmation 类型变更
- `frontend/src/lib/hooks/useChatSession.ts` -- 状态流转与折叠定时器
- `frontend/src/components/chat/confirmation-card.tsx` -- 组件重构
- `frontend/src/components/chat/message-item.tsx` -- 渲染条件调整
- `frontend/src/lib/i18n/strings.ts` -- 确认卡片 i18n 文案
- `frontend/src/styles/chat.css` -- 动画与样式
