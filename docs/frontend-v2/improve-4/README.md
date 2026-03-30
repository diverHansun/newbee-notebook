# Frontend-v2 改进计划 4 - Notebook 卡片右键菜单与视觉重设计

## 概述

本文档集描述了 Newbee Notebook 前端 v2 的第四轮改进，包含两个相互关联的部分：

1. **右键菜单与编辑功能** - 鼠标右击 Notebook 卡片，弹出上下文菜单，支持编辑 Notebook 名称与描述，以及删除操作
2. **卡片视觉重设计** - 移除底部操作栏，优化卡片悬停状态，提升整体视觉质量

## 背景

当前 Notebook 的名称和描述在创建后无法修改，用户只能删除并重建。同时卡片底部的删除按钮占用了独立的空间区域，视觉上与卡片内容割裂。将操作整合进右键菜单可以同时解决这两个问题。

## 技术现状

后端更新接口已完整实现，本次改进为纯前端工作：

| 层级 | 状态 | 说明 |
|------|------|------|
| 后端 PATCH 端点 | 已就绪 | `PATCH /api/v1/notebooks/{notebook_id}` |
| 后端 Service / Repository | 已就绪 | 支持 title / description 部分更新 |
| 前端 API 函数 | 已就绪 | `updateNotebook()` 已定义，未被调用 |
| 前端 UI | 待实现 | 右键菜单、编辑 Modal、卡片样式 |

## 文档结构

| 文档 | 职责 |
|------|------|
| README.md | 本文档，概述与背景 |
| 01-context-menu.md | 右键菜单的交互设计与实现规范 |
| 02-edit-modal.md | 编辑 Modal 的表单设计与 API 集成规范 |
| 03-card-visual-redesign.md | 卡片视觉重设计的样式规范 |
| 04-implementation-plan.md | 实现步骤与文件修改清单 |

## 模块关系

```
notebooks/page.tsx
    |
    |-- NotebookContextMenu (新增组件)
    |       |-- 触发：onContextMenu 事件
    |       |-- 菜单项：编辑信息 / 删除
    |
    |-- EditNotebookModal (新增状态 + Modal)
    |       |-- 调用：updateNotebook() [已有]
    |       |-- 成功后：invalidateQueries
    |
    |-- notebook-card (样式重设计)
            |-- 去除：notebook-card-footer
            |-- 新增：hover 时的 ··· 提示指示器
            |-- 优化：hover 状态、字重、内边距
```

## 设计原则

- **可发现性优先**：右键菜单是非标准的 Web 交互，必须通过 hover 指示器给用户视觉提示
- **复用已有模式**：编辑 Modal 与创建 Notebook 的 Modal 保持一致的交互风格
- **沿用 CSS 体系**：新增样式使用项目已有的 CSS 变量和 class 命名规范，不引入新的样式库
- **最小改动原则**：后端无需修改，前端只在 `page.tsx` 和 `cards.css` 上集中修改
