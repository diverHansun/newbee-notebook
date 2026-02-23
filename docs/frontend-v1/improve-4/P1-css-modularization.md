# P1: CSS 模块化

## 问题描述

`frontend/src/app/globals.css` 当前共 1244 行，所有样式混写在单一文件中。具体问题：

1. 单文件过长，查找特定组件样式需要全局搜索
2. 多人协作时修改同一文件极易产生冲突
3. 无法按功能域做代码审查
4. 已有 `@import "../styles/markdown-content.css"` 说明拆分机制存在，但未充分利用

## 当前实现

```
frontend/src/
  app/
    globals.css          ← 1244 行单文件
  styles/
    markdown-content.css ← 已有，保留
```

`globals.css` 内部按注释分为 23 个逻辑节，依次是：CSS 变量、Base reset、Layout、Panel、Flex、Button、Input、Chat input、Source selector、Badge/Chip、List、Card、Overlay、Muted、Notebook grid、Tab bar、Data table、Empty state、Bottom bar、Selection menu、Resize handle、Skeleton、Explain card、Thinking indicator、Responsive breakpoints。

## 设计原则

1. **输出不变**：拆分后所有 CSS 类名、`--css-variable` 名称均保持不变，禁止在拆分过程中修改任何样式值
2. **快照保护**：拆分前为当前 `globals.css` 保留一份快照（见下文），作为回滚和目视对比基准
3. **单一职责**：每个分区文件对应一个功能域，文件间不重复声明同一个类
4. **扁平导入**：所有分区文件统一由 `globals.css` 一层 `@import`，不允许分区文件互相 `@import`

## 目标目录结构

```
frontend/src/
  app/
    globals.css              ← 保留 Tailwind 指令 + CSS 变量 + 全部 @import（约 100 行）
  styles/
    markdown-content.css     ← 已有，保留不动
    _snapshot.css            ← 拆分前完整快照（只读，不参与构建）
    base.css                 ← Body reset、基础 typography、滚动条
    layout.css               ← page-shell、workspace-grid、panel、app-shell
    buttons.css              ← .btn 及所有变体（primary、ghost、destructive、sm、icon）
    inputs.css               ← .input、.textarea、.select、.segmented-control
    badges.css               ← .badge 及所有变体、.chip
    cards.css                ← .card、.message-bubble-assistant、.overlay
    chat.css                 ← 所有 .chat-* 类（输入区、工具栏、chips）
    sources.css              ← .sources-*、source-ref-btn、source selector panel
    reader.css               ← selection-menu、explain-card、resize-handle
    thinking-indicator.css   ← .thinking-indicator 及其动画
    animations.css           ← 全部 @keyframes（与组件解耦，便于共享）
    utilities.css            ← .muted、.row、.stack-*、.page-header 等通用工具类
    responsive.css           ← 所有 @media 断点规则
```

## 快照策略

拆分开始前执行：

```powershell
Copy-Item frontend/src/app/globals.css frontend/src/styles/_snapshot.css
```

`_snapshot.css` 用途：
- 拆分过程中的目视对比参考（diff 确认无遗漏）
- 出现样式回归时快速定位原始规则
- 不被 `globals.css` `@import`，不参与实际构建

`_snapshot.css` 顶部加注释：

```css
/*
 * SNAPSHOT: globals.css 拆分前快照（improve-4 / P1）
 * 此文件仅用于参考和回滚，不参与构建，不可修改。
 */
```

## 拆分后 globals.css 结构

```css
/* ================================================================
   Tailwind 指令（必须放在最顶部）
   ================================================================ */
@tailwind base;
@tailwind components;
@tailwind utilities;

/* ================================================================
   外部库
   ================================================================ */
@import "katex/dist/katex.min.css";

/* ================================================================
   CSS 变量 — Light / Dark 主题（保留在本文件，避免变量定义分散）
   ================================================================ */
:root { ... }
.dark { ... }

/* ================================================================
   样式分区 @import
   ================================================================ */
@import "../styles/base.css";
@import "../styles/layout.css";
@import "../styles/buttons.css";
@import "../styles/inputs.css";
@import "../styles/badges.css";
@import "../styles/cards.css";
@import "../styles/utilities.css";
@import "../styles/chat.css";
@import "../styles/sources.css";
@import "../styles/reader.css";
@import "../styles/thinking-indicator.css";
@import "../styles/animations.css";
@import "../styles/responsive.css";
@import "../styles/markdown-content.css";
```

CSS 变量（`:root` 和 `.dark`）保留在 `globals.css` 本体中，不单独拆出，原因是 Tailwind 的 `@tailwind base` 需要它们在同一处理上下文中被识别。

## 各分区说明

| 文件 | 包含内容 | 预估行数 |
|------|----------|---------|
| `base.css` | `*` reset、`body`、`html`、滚动条（webkit） | ~30 |
| `layout.css` | `.page-shell`、`.workspace-grid`、`.panel`、`.notebook-grid`、`.tab-bar`、`.bottom-bar` | ~120 |
| `buttons.css` | `.btn`、`.btn-primary`、`.btn-ghost`、`.btn-destructive`、`.btn-sm`、`.btn-icon`、`.chat-action-btn` | ~80 |
| `inputs.css` | `.input`、`.textarea`、`.select`、`.segmented-control` | ~70 |
| `badges.css` | `.badge`、所有 `.badge-*` 变体、`.chip` | ~60 |
| `cards.css` | `.card`、`.message-bubble-assistant`、`.overlay`、`.data-table` | ~50 |
| `chat.css` | `.chat-input-shell`、`.chat-input-container`、`.chat-input-toolbar`、`.chat-input-source-chips`、消息气泡相关 | ~120 |
| `sources.css` | `.sources-panel`、`.source-ref-btn`、`.source-card`、`.source-list`、源 selector 面板 | ~80 |
| `reader.css` | `.selection-menu`、`.explain-card`、`.explain-card-*`、`.resize-handle`、`.explain-card-pill` | ~100 |
| `thinking-indicator.css` | `.thinking-indicator` 及子元素 | ~50 |
| `animations.css` | 全部 `@keyframes`（`thinking-spin`、`thinking-shimmer`、`thinking-fade-out`、`skeleton-shimmer` 等） | ~60 |
| `utilities.css` | `.muted`、`.row`、`.stack-sm`、`.stack-md`、`.empty-state`、`.skeleton`、`.page-header` | ~80 |
| `responsive.css` | `@media (max-width: 1024px)`、`@media (max-width: 768px)` | ~60 |

合计约 960 行（分散到 13 个文件），`globals.css` 本体约 100 行（变量 + imports）。

## 实施步骤

1. 执行快照命令，生成 `_snapshot.css`
2. 按分区逐一将对应代码段剪切到目标文件
3. 每完成一个分区，启动 `pnpm dev` 目视检查无样式丢失
4. 全部完成后，对比 `_snapshot.css` 与 `styles/` 目录下所有文件的行数总和，确认无遗漏
5. 运行 `pnpm typecheck` 确认无 TypeScript 报错（CSS Modules 不涉及，但 import 路径变更可能影响工具链）

## 涉及文件

| 文件 | 操作 |
|------|------|
| `frontend/src/app/globals.css` | 重写为约 100 行的导入汇总文件 |
| `frontend/src/styles/_snapshot.css` | 新增，只读快照 |
| `frontend/src/styles/*.css`（13 个） | 新增，各分区样式 |

## 验证标准

- 所有页面视觉与拆分前完全一致（以 `_snapshot.css` 为参考基准）
- `pnpm build` 无报错，无 CSS 丢失告警
- `globals.css` 本体不超过 120 行
- 每个分区文件不超过 150 行
- 无任何样式值被修改（纯搬运，零修改）
