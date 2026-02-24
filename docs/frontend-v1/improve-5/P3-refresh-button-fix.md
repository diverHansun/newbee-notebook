# P3: Sources 面板"刷新"按钮交互修复

## 问题描述

Notebook 详情页左侧 Sources 面板中，"刷新"按钮在鼠标 hover 和 click 时缺乏明显的视觉反馈，与旁边的"+ 添加"按钮的交互体验不一致。

## 根因分析

两个按钮的 CSS 类名不同：

| 按钮 | CSS 类名 | hover 行为 | active 行为 |
|------|---------|-----------|------------|
| + 添加 | `btn btn-sm` | 背景色变为 `--accent`，边框色变为 `--ring` | `transform: scale(0.95)` |
| 刷新 | `btn btn-ghost btn-sm` | 背景色变为 `--accent`，边框保持透明 | `transform: scale(0.95)` |

从 CSS 定义看，`.btn-ghost:hover` 确实设置了 `background: hsl(var(--accent))`，理论上有 hover 效果。但由于 ghost 按钮的初始状态完全透明（无背景、无边框），hover 时仅出现轻微的背景色变化而没有边框变化，视觉反馈弱于普通 `.btn`。

对比效果：
- `.btn:hover`：背景色变化 + 边框高亮（双重反馈）
- `.btn-ghost:hover`：仅背景色变化（单一反馈，且 accent 色本身较浅）

## 修复方案

有两种可选方案：

### 方案 A：调整按钮类名（推荐）

将"刷新"按钮的类名从 `btn btn-ghost btn-sm` 改为 `btn btn-sm`，使其与"+ 添加"按钮的交互行为完全一致。

```tsx
// source-list.tsx 第 104-110 行
// 修改前
<button
  className="btn btn-ghost btn-sm"
  type="button"
  onClick={() => notebookDocumentsQuery.refetch()}
>
  {t(uiStrings.sourceList.refresh)}
</button>

// 修改后
<button
  className="btn btn-sm"
  type="button"
  onClick={() => notebookDocumentsQuery.refetch()}
>
  {t(uiStrings.sourceList.refresh)}
</button>
```

**影响**：刷新按钮将从完全透明变为有背景色和边框的常规按钮样式。视觉上与"+ 添加"按钮一致，形成统一的按钮组。

### 方案 B：增强 ghost 按钮的 hover 效果

在 `buttons.css` 中为 `.btn-ghost:hover` 增加边框反馈：

```css
.btn-ghost:hover {
  background: hsl(var(--accent));
  border-color: hsl(var(--border));  /* 新增：hover 时显示边框 */
}
```

**影响**：所有使用 `btn-ghost` 的按钮都会获得增强的 hover 效果，需要全局检查是否有副作用。

## 推荐方案

采用**方案 A**，理由：
1. 改动最小，仅修改一个 className
2. "刷新"和"添加"按钮功能并列，视觉应一致
3. 不影响其他使用 `btn-ghost` 的组件（如删除按钮等，ghost 样式对它们是合理的）

## 涉及文件

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `components/sources/source-list.tsx` | 修改 | 第 105 行 className 调整 |

## 验证方式

1. hover "刷新"按钮时出现与"+ 添加"相同的背景色变化和边框高亮
2. 点击"刷新"按钮时出现 `scale(0.95)` 缩放效果
3. 点击后 Sources 列表正确刷新（功能无退化）
