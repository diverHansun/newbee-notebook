# 实现计划

## 涉及文件

| 文件 | 操作类型 | 说明 |
|------|---------|------|
| `frontend/src/app/notebooks/page.tsx` | 修改 | 主要改动文件：状态、菜单触发、编辑 Modal |
| `frontend/src/styles/cards.css` | 修改 | 卡片样式重设计 |
| `frontend/src/lib/i18n/strings.ts` | 修改 | 新增编辑相关 i18n 字符串 |
| `frontend/src/components/notebooks/` | 新增 | `NotebookContextMenu` 组件 |
| `frontend/src/app/notebooks/page.test.tsx` | 新增或修改 | 覆盖新增交互的单元测试 |

后端文件无需修改。

## 实现步骤

### 步骤 1：卡片样式重设计

先做样式，再做功能，可以更早看到视觉效果。

- 修改 `cards.css`：
  - 移除 `.notebook-card-footer` 规则
  - 移除 `.notebook-card` 的 `min-height: 176px`
  - 更新 `.notebook-card-link`：调整 padding，添加 `position: relative`
  - 添加 `.notebook-card:hover` 增强规则
  - 添加 `.notebook-card-menu-hint` 及其 hover 显示规则
  - 移除 `.notebook-card-title` 的 `font-size: 15px`
- 修改 `page.tsx`：
  - 移除 `<div className="notebook-card-footer">` JSX 及其内部删除按钮
  - 将标题的 `font-medium` 改为 `font-semibold`
  - 在 `.notebook-card-link` 内部添加 `<span className="notebook-card-menu-hint">···</span>`

### 步骤 2：新增 i18n 字符串

在 `strings.ts` 的 `notebooksPage` 对象下新增编辑相关条目（详见 02-edit-modal.md）。

### 步骤 3：实现 NotebookContextMenu 组件

在 `frontend/src/components/notebooks/` 下新建 `notebook-context-menu.tsx`：

- 使用 `ReactDOM.createPortal` 挂载到 `document.body`
- 接收位置坐标和回调 props（详见 01-context-menu.md）
- 内部处理关闭逻辑（`mousedown` 事件、`Escape` 键、`scroll` 事件）
- 样式使用 01-context-menu.md 中定义的 CSS 类

### 步骤 4：在 page.tsx 中集成右键菜单

- 新增 `contextMenu` 状态
- 在 `.notebook-card` 上添加 `onContextMenu` 事件处理
- 渲染 `NotebookContextMenu` 组件
- 菜单"删除"项调用已有的 `setPendingDeleteNotebook`

### 步骤 5：实现编辑 Modal

- 新增 `editingNotebook` 状态
- 新增 `updateMutation`（调用 `updateNotebook()`）
- 复用现有 Modal 结构，渲染 title / description 表单
- 实现前端校验逻辑（详见 02-edit-modal.md）
- 成功后 invalidate queries 刷新列表

### 步骤 6：完善测试

针对以下场景补充测试：

- 右键卡片后菜单出现，包含"编辑信息"和"删除"两项
- 点击"编辑信息"后 Modal 打开，预填当前 title 和 description
- 清空 title 后保存按钮不可用
- 保存成功后 Modal 关闭，列表刷新
- 点击菜单外部后菜单关闭
- 按 Escape 键后菜单关闭

## 实现顺序说明

按步骤 1 到 5 顺序实现，每步独立可验证。步骤 1 完成后即可在浏览器中确认视觉效果；步骤 3 完成后可独立测试菜单组件；步骤 4、5 在 page.tsx 中串联，最后统一测试。

## 注意事项

- `NotebookContextMenu` 使用 Portal 挂载，需确认项目中 `document` 可用（Next.js 客户端组件，加 `"use client"` 指令）
- 右键菜单的 `z-index: 200` 需高于 Modal 的遮罩层（通常为 `z-index: 50`），避免菜单被遮罩覆盖
- description 字段空值处理：用户清空后传 `null`，不传空字符串
- 编辑成功的 query key 为 `["notebooks"]`，与列表查询保持一致
