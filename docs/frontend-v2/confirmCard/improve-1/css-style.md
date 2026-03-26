# CSS 动画与样式规范

## 概述

本文档定义 ConfirmationCard 优化涉及的 CSS 变更, 包括状态过渡动画、危险操作样式、内联标签样式。

## 卡片基础样式

保留现有 `.confirmation-card` 基础样式, 新增 `data-action-type` 属性驱动的变体。

### 现有样式 (保留)

```css
.confirmation-card {
  margin-top: 8px;
  border: 1px solid hsl(var(--border));
  border-radius: 10px;
  background: hsl(var(--accent));
  padding: 12px;
}
```

### 移除的信息区域

倒计时和 requestId 行不再显示, 相关 CSS 可保留但不会被使用。

## 状态动画

### pending 状态

默认显示, 无特殊动画:

```css
.confirmation-card--pending {
  opacity: 1;
  transform: translateY(0);
}
```

### resolving 状态 (confirmed / rejected / timeout)

卡片短暂显示结果后 fade out:

```css
.confirmation-card--resolving {
  animation: confirmation-fade-out 1.5s ease-out forwards;
  pointer-events: none;
}

@keyframes confirmation-fade-out {
  0% {
    opacity: 1;
    transform: translateY(0);
  }
  60% {
    opacity: 1;
    transform: translateY(0);
  }
  100% {
    opacity: 0;
    transform: translateY(-4px);
    max-height: 0;
    margin: 0;
    padding: 0;
    overflow: hidden;
  }
}
```

动画时间线:
- 0% ~ 60% (0 ~ 0.9s): 保持完全可见, 用户可阅读结果状态
- 60% ~ 100% (0.9s ~ 1.5s): 渐隐 + 轻微上移, 同时收缩高度

`pointer-events: none` 防止动画期间误触。

## 危险操作样式

通过 `data-action-type="delete"` 属性选择器驱动:

```css
/* 删除操作 -- 红色边框 */
.confirmation-card[data-action-type="delete"] {
  border-color: hsl(var(--destructive) / 0.5);
  background: hsl(var(--destructive) / 0.04);
}

/* 删除操作 -- 红色确认按钮 */
.confirmation-card[data-action-type="delete"] .btn-confirm,
.confirmation-card[data-action-type="delete"] .btn-destructive {
  background: hsl(var(--destructive));
  color: hsl(var(--destructive-foreground));
  border-color: hsl(var(--destructive));
}

.confirmation-card[data-action-type="delete"] .btn-confirm:hover,
.confirmation-card[data-action-type="delete"] .btn-destructive:hover {
  background: hsl(var(--destructive) / 0.9);
}
```

### 非危险操作

create / update / confirm 操作保持默认样式, 不需要额外 CSS 规则。

## 内联标签样式

collapsed 状态渲染的 `ConfirmationInlineTag`:

```css
.confirmation-inline-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: hsl(var(--muted-foreground));
  margin-top: 6px;
  padding: 2px 0;
}

/* 已确认 -- 使用成功色 */
.confirmation-inline-tag[data-status="confirmed"] {
  color: hsl(var(--success, 142 71% 45%));
}

/* 已拒绝 -- 保持灰色 */
.confirmation-inline-tag[data-status="rejected"] {
  color: hsl(var(--muted-foreground));
}

/* 已超时 -- 使用警告色 */
.confirmation-inline-tag[data-status="timeout"] {
  color: hsl(var(--warning, 38 92% 50%));
}
```

注意: `--success` 和 `--warning` CSS 变量可能未在项目中定义, 此处提供回退值。实现时应检查项目主题中是否已有这些变量, 如无则使用回退值。

## CSS 变量依赖

本方案依赖以下 CSS 变量 (均为项目现有变量):

| 变量 | 用途 |
|------|------|
| `--border` | 卡片默认边框色 |
| `--accent` | 卡片默认背景色 |
| `--destructive` | 危险操作边框和按钮色 |
| `--destructive-foreground` | 危险按钮文字色 |
| `--muted-foreground` | 内联标签默认色 |

可能需要新增:

| 变量 | 用途 | 回退值 |
|------|------|--------|
| `--success` | 已确认标签色 | `142 71% 45%` |
| `--warning` | 已超时标签色 | `38 92% 50%` |

## GPU 加速

动画仅使用 `opacity` 和 `transform` 属性 (GPU 加速), `max-height` 仅在动画末尾帧使用以收缩占位空间。这与项目中 progress-bar 的动画策略保持一致。
