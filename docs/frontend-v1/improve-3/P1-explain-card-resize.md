# P1: Explain/Conclude 卡片尺寸调整

## 问题描述

Explain/Conclude 浮动卡片的默认尺寸为 400x380px，竖直方向空间不足，用户阅读解释或总结内容时需要频繁滚动。水平方向也偏窄，长句容易折行。

## 当前实现

文件：`frontend/src/components/chat/explain-card.tsx` 第 15-16 行

```typescript
const DEFAULT_WIDTH = 400;
const DEFAULT_HEIGHT = 380;
```

`useResizable` 约束：
```typescript
minSize: { width: 300, height: 180 }
maxSize: { width: 600, height: 500 }
```

## 实现目标

```typescript
const DEFAULT_WIDTH = 520;
const DEFAULT_HEIGHT = 680;

// useResizable 约束同步调整
minSize: { width: 380, height: 400 }
maxSize: { width: 720, height: 900 }
```

## 实现要点

### 1. 尺寸常量修改

修改 `explain-card.tsx` 中的四组数值即可。

### 2. 视口溢出保护

卡片锚定在 main-panel 右上角。增大默认高度后，当视口较小时卡片可能超出底部边界。需要在计算卡片位置时加入约束：

```typescript
// anchorTop：通过 main-panel 容器的 getBoundingClientRect().top 获取，
// 即卡片锚点（右上角图标）相对于视口顶部的 Y 偏移量。
const maxHeight = Math.min(size.height, window.innerHeight - anchorTop - 16);
```

将此 `maxHeight` 应用到 `<aside>` 的 `height` 样式上，同时保持 body 区域的 `overflow: auto` 确保内容可滚动。

> **多分辨率适配**：`window.innerHeight - anchorTop` 的计算在 768p、1080p 及以上分辨率均适用，不需要为特定分辨率编写专用逻辑。

### 3. CSS 样式确认

`globals.css` 中 `.explain-card` 的样式不依赖固定尺寸，无需调整。`.explain-card-body` 已有 `flex: 1` 和 `overflow: auto`，自动适应高度变化。

## 涉及文件

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/components/chat/explain-card.tsx` | 四组尺寸常量 + 视口溢出保护 |

## 验证标准

- 卡片默认展开尺寸为 520x680
- 在 768p（笔记本）和 1080p（桌面）两种分辨率下，卡片不超出视口底部
- 拖拽缩放功能正常，最小/最大约束生效
- 内容超出 body 区域时可正常滚动

> P3 升级全局圆角后，`.explain-card` 的 `border-radius` 会跟随 `.card` 的新值（10px）自动更新，无需在本任务中单独处理。
