# Batch-3 前端设计文档

## 模块概述

Batch-3 前端为 Markdown Viewer 引入书签标注能力，将 Studio Panel 从占位状态升级为 Notes & Marks 管理面板，并在 Chat 中支持 Skill 的 slash 命令提示和确认交互。

## 文档索引

| 文档 | 内容 |
|------|------|
| 01-markdown-viewer-bookmark.md | Markdown Viewer 书签集成：创建书签、边距图标展示、跨面板联动 |
| 02-studio-panel.md | Studio Panel 设计：卡片网格首屏、Notes & Marks 视图、Note 编辑器、Mark 引用插入 |
| 03-skill-frontend.md | Skill 前端交互：slash 命令提示、SSE 确认事件处理、内联确认卡片、确认回传 API |
| 04-i18n-and-types.md | 国际化字符串规划与 TypeScript 类型定义 |
| 05-test.md | 前端测试策略 |

## 与其他模块的关系

- 后端 API 依赖：`docs/backend-v2/batch-3/note-bookmark/04-api-layer.md` 定义的 REST 接口
- 后端 SSE 事件依赖：`docs/backend-v2/batch-3/note-related-skills/04-activation-and-confirmation.md` 定义的 ConfirmationRequestEvent
- 前端现有组件基础：SelectionMenu、MarkdownViewer、ChatInput、MessageItem、ConfirmDialog

## 设计原则

- 最小侵入：不修改现有 rehype 渲染管道和 useTextSelection hook 签名
- 模式复用：新组件复用现有 CSS 类（.card、.badge、.source-selector-panel 等）和 Zustand + TanStack Query 数据管理模式
- 国际化：所有用户可见文本通过 uiStrings 管理，支持中英文
- 跨面板联动：通过 Zustand store 实现 Reader、Studio、Chat 三面板的状态通信
