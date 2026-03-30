# 卡片视觉重设计规范

## 改动概览

| 编号 | 改动项 | 文件 |
|------|--------|------|
| 1 | 移除 notebook-card-footer | cards.css + page.tsx |
| 2 | 新增 hover 时 ··· 指示器 | cards.css + page.tsx |
| 3 | 增强 hover 状态 | cards.css |
| 4 | 标题字重升级 | page.tsx |
| 5 | 调整内边距 | cards.css |

## 改动 1：移除 notebook-card-footer

操作整合进右键菜单后，卡片底部的操作栏不再需要。删除 `cards.css` 中的 `.notebook-card-footer` 规则，并移除 `page.tsx` 中对应的 JSX 元素（`<div className="notebook-card-footer">`）。

移除前卡片结构：
```
.notebook-card
  .notebook-card-link    (内容区)
  .notebook-card-footer  (操作区，含删除按钮)
```

移除后卡片结构：
```
.notebook-card
  .notebook-card-link    (内容区，撑满整张卡片)
```

同时去掉 `.notebook-card` 的 `min-height: 176px`，让高度由内容自然撑开。

## 改动 2：新增 hover 时的 ··· 指示器

在 `.notebook-card-link` 内部右上角插入一个提示元素，仅在卡片 hover 时显示，告知用户可以右键操作。

JSX 结构（追加在 `.notebook-card-link` 内部）：

```tsx
<span className="notebook-card-menu-hint" aria-hidden="true">···</span>
```

CSS 规则：

```css
.notebook-card-menu-hint {
  position: absolute;
  top: 10px;
  right: 14px;
  font-size: 16px;
  letter-spacing: 1px;
  color: hsl(var(--muted-foreground));
  opacity: 0;
  transition: opacity 150ms ease;
  pointer-events: none;
  user-select: none;
}

.notebook-card:hover .notebook-card-menu-hint {
  opacity: 1;
}
```

`.notebook-card-link` 需补充 `position: relative` 以使绝对定位的提示元素相对卡片定位（当前已有 padding，需确认是否已设置，若无则补充）。

## 改动 3：增强 hover 状态

当前 `.card-interactive:hover` 仅有 `translateY(-1px)`，视觉反馈较弱。将 notebook 卡片的 hover 增强单独处理，不影响其他使用 `.card-interactive` 的卡片：

```css
/* 在现有 .card:hover 之后追加 */
.notebook-card:hover {
  transform: translateY(-2px);
  border-color: hsl(var(--bee-yellow) / 0.4);
  box-shadow:
    0 6px 12px -2px rgba(0, 0, 0, 0.1),
    0 3px 6px -2px rgba(0, 0, 0, 0.06);
}
```

使用品牌色 `--bee-yellow` 作为 hover 描边颜色，与项目整体风格保持一致。

## 改动 4：标题字重升级

在 `page.tsx` 中，将 `notebook-card-title` 的 className 从 `font-medium` 改为 `font-semibold`：

```tsx
// 修改前
<strong className="text-sm font-medium notebook-card-title" ...>

// 修改后
<strong className="text-sm font-semibold notebook-card-title" ...>
```

同时在 `cards.css` 中去掉 `.notebook-card-title` 的 `font-size: 15px`，改由 `text-sm`（14px）统一控制，与项目字号体系保持一致。

## 改动 5：调整内边距

将 `.notebook-card-link` 的内边距从 `padding: 22px` 调整为 `padding: 16px 20px`，使卡片内容区更紧凑，网格整体视觉更均衡。顶部保留额外空间供 ··· 指示器使用：

```css
.notebook-card-link {
  display: flex;
  flex: 1;
  flex-direction: column;
  padding: 16px 20px;
  position: relative; /* 供 ··· 指示器绝对定位 */
}
```

## 完整 CSS 变更汇总

以下为 `cards.css` 中涉及 notebook 卡片部分的最终状态（仅列出有改动的规则）：

```css
.notebook-card {
  display: flex;
  flex-direction: column;
  /* 移除 min-height: 176px */
}

.notebook-card-link {
  display: flex;
  flex: 1;
  flex-direction: column;
  padding: 16px 20px;   /* 原 22px */
  position: relative;   /* 新增 */
}

.notebook-card-title {
  /* 移除 font-size: 15px，由 text-sm 控制 */
}

.notebook-card:hover {
  transform: translateY(-2px);
  border-color: hsl(var(--bee-yellow) / 0.4);
  box-shadow:
    0 6px 12px -2px rgba(0, 0, 0, 0.1),
    0 3px 6px -2px rgba(0, 0, 0, 0.06);
}

.notebook-card-menu-hint {
  position: absolute;
  top: 10px;
  right: 14px;
  font-size: 16px;
  letter-spacing: 1px;
  color: hsl(var(--muted-foreground));
  opacity: 0;
  transition: opacity 150ms ease;
  pointer-events: none;
  user-select: none;
}

.notebook-card:hover .notebook-card-menu-hint {
  opacity: 1;
}

/* 删除以下规则 */
/* .notebook-card-footer { ... } */
```
