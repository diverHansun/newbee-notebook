# Frontend V1 - Improve-1 优化方案总览

## 概述

本轮优化针对 frontend-v1 初始实现中发现的四类前端问题进行根因分析和修复方案设计。
所有问题均经过前后端代码级别的详细调查，确认了根本原因后才提出解决方案。

## 问题清单

| 编号 | 问题 | 严重程度 | 需后端改动 | 文档 |
|------|------|----------|------------|------|
| 01 | Markdown 阅读器滚动卡顿 | 高 | 否 | [01-markdown-scroll-optimization.md](01-markdown-scroll-optimization.md) |
| 02 | Explain/Conclude 创建多余会话 | 中 | 否 | [02-session-mode-filtering.md](02-session-mode-filtering.md) |
| 03 | View 按钮状态判断逻辑 | -- | -- | [03-view-button-status.md](03-view-button-status.md) |
| 04 | 删除操作缺少二次确认 | 高 | 否 | [04-delete-confirmation.md](04-delete-confirmation.md) |

问题 03 经前后端代码确认，前端逻辑已正确，后端限制已在提交 `224b968` 中修复，
当前无需改动。详见文档中的待确认事项。

## 涉及文件总览

### 问题 01 涉及文件

```
frontend/src/lib/hooks/useTextSelection.ts        -- 滚动事件监听（主要卡顿源）
frontend/src/components/reader/markdown-viewer.tsx -- Markdown 渲染组件（未 memo）
frontend/src/components/reader/markdown-pipeline.ts -- Markdown 转 HTML 管线
frontend/src/components/reader/document-reader.tsx  -- 文档阅读容器（滚动容器）
frontend/src/styles/markdown-content.css            -- 样式与动画（shimmer）
```

### 问题 02 涉及文件

```
frontend/src/lib/hooks/useChatSession.ts            -- ensureSession 逻辑（改动点）
参考: newbee_notebook/core/engine/session.py        -- 后端双缓冲区设计
```

问题 02 的根因已修正: 后端设计为四种模式共享同一 Session（双缓冲区隔离上下文），
前端不应为 explain/conclude 创建新会话。修改集中在 `useChatSession.ts` 一个文件。

### 问题 03 涉及文件（仅供参考，无需改动）

```
frontend/src/components/sources/source-card.tsx     -- View 按钮（逻辑已正确）
frontend/src/components/reader/document-reader.tsx  -- 内容获取（逻辑已正确）
后端: newbee_notebook/application/services/document_service.py -- 已修复 converted 限制
```

### 问题 04 涉及文件

```
frontend/src/app/notebooks/page.tsx                 -- 删除 Notebook
frontend/src/components/sources/source-card.tsx     -- 移除文档（样式也需修改）
frontend/src/components/chat/chat-panel.tsx         -- 删除会话
frontend/src/app/library/page.tsx                   -- 删除/彻底删除/批量删除文档
（新建）frontend/src/components/ui/confirm-dialog.tsx -- 确认对话框组件
```

## 修改原则

1. 最小化改动范围，不引入不必要的重构
2. 所有修改均为纯前端改动，不需要后端配合
3. 每项修改完成后需通过手动验证确认效果

## 实施顺序建议

1. **问题 04（删除确认）** -- 改动最小，风险最低，安全性和用户体验提升明显
2. **问题 01（滚动优化）** -- 核心体验问题，改动集中在几个文件
3. **问题 02（会话复用）** -- 仅需改动 useChatSession.ts 中的 ensureSession 逻辑
4. **问题 03（View 按钮）** -- 待确认是否仍可复现
