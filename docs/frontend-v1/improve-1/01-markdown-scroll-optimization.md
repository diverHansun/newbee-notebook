# 01 - Markdown 阅读器滚动卡顿优化

## 当前问题

在 Markdown 阅读器中滚动文档时存在明显卡顿，特别是在长文档和包含大量图片的场景下。
通过代码级别的根因分析，确定了以下具体原因（按严重程度排序）。

## 根因分析

### 根因 1（严重）: 滚动事件无节流

**位置:** `frontend/src/lib/hooks/useTextSelection.ts:59`

```typescript
window.addEventListener("scroll", hideMenu, true);
```

`hideMenu` 在每次滚动事件触发时执行，没有任何节流（throttle）或防抖（debounce）。
滚动时浏览器每秒触发 60 次以上滚动事件，每次都会更新 Zustand store，
进而触发组件树重渲染。这是卡顿的首要原因。

### 根因 2（严重）: 滚动容器与监听对象不匹配

**位置:**
- 监听目标: `window`（`useTextSelection.ts:59`）
- 位置计算: `window.scrollY`（`useTextSelection.ts:46-48`）
- 实际滚动容器: `document-reader.tsx:155` 中的 `<div style={{ overflow: "auto" }}>`

实际滚动发生在 DocumentReader 内部的 div 上，而事件监听挂在 window 上。
内部容器滚动时 `window.scrollY` 始终为 0，导致位置计算错误，
同时由于事件冒泡机制（`useCapture=true`），每次内部滚动仍会触发 window 级别的处理函数。

### 根因 3（严重）: MarkdownViewer 未做渲染保护

**位置:** `frontend/src/components/reader/markdown-viewer.tsx:61`

```typescript
export function MarkdownViewer({ content, documentId, className, containerRef }: MarkdownViewerProps) {
  // 未使用 React.memo
```

MarkdownViewer 未用 `React.memo` 包裹。
上层 DocumentReader 因滚动事件触发 store 更新而重渲染时，
MarkdownViewer 会跟随重渲染，即使其 props 没有任何变化。

### 根因 4（中等）: 图片 shimmer 动画未使用 GPU 加速

**位置:** `frontend/src/styles/markdown-content.css:258-272`

```css
.markdown-content img[data-loaded="0"]:not([src=""]) {
  animation: img-shimmer 1.5s infinite;
}
@keyframes img-shimmer {
  to { background-position: -200% 0; }
}
```

动画使用 `background-position` 属性驱动。该属性变化无法触发 GPU 合成层优化，
每帧都需要 CPU 重绘（repaint）。当页面中存在多个正在加载的图片时，
连续动画帧与滚动帧竞争主线程资源。

### 根因 5（中等）: IntersectionObserver 预加载距离过大

**位置:** `frontend/src/components/reader/markdown-viewer.tsx:88`

```typescript
{ root: null, rootMargin: "600px 0px" }
```

预加载触发距离为 600px，在快速滚动时会频繁触发 Markdown 渲染管线
（unified + remark + rehype 全链路处理），每次处理约 24KB 的 HTML 块，
与用户滚动帧竞争主线程时间。

### 根因 6（低）: 图片 onerror/onload 使用内联 JS

**位置:** `frontend/src/components/reader/markdown-pipeline.ts:67-74`

图片的 `onerror` 和 `onload` 通过内联字符串注入，在图片加载完成时同步执行 DOM 操作。
多张图片同时加载时会在主线程上排队执行。

## 解决方案

### 修改 1: 为滚动事件添加 requestAnimationFrame 节流

**文件:** `frontend/src/lib/hooks/useTextSelection.ts`

将 `hideMenu` 的滚动事件处理改为 `requestAnimationFrame` 节流模式，
确保每帧最多执行一次。

```typescript
// 修改前
window.addEventListener("scroll", hideMenu, true);

// 修改后
let rafId = 0;
const throttledHideMenu = () => {
  if (rafId) return;
  rafId = requestAnimationFrame(() => {
    hideMenu();
    rafId = 0;
  });
};
window.addEventListener("scroll", throttledHideMenu, true);

// cleanup 中同步取消
return () => {
  cancelAnimationFrame(rafId);
  window.removeEventListener("scroll", throttledHideMenu, true);
};
```

### 修改 2: 修正滚动容器监听目标

**文件:** `frontend/src/lib/hooks/useTextSelection.ts` 和 `frontend/src/components/reader/document-reader.tsx`

方案: 将 containerRef 传入 useTextSelection，用 `containerRef.current` 代替 `window` 作为滚动监听目标。
位置计算中的 `window.scrollY` / `window.scrollX` 改为读取容器的 `scrollTop` / `scrollLeft`。

具体改动:
1. `useTextSelection` 接收一个可选的 `scrollContainerRef` 参数
2. 滚动监听挂在 `scrollContainerRef.current ?? window` 上
3. 位置计算使用容器的 scroll 偏移量

### 修改 3: 为 MarkdownViewer 添加 React.memo

**文件:** `frontend/src/components/reader/markdown-viewer.tsx`

```typescript
// 修改前
export function MarkdownViewer(...) { ... }

// 修改后
export const MarkdownViewer = memo(function MarkdownViewer(...) { ... });
```

因为 `content`、`documentId` 在文档不变时是稳定引用，
`React.memo` 的浅比较即可有效阻止无意义的重渲染。

### 修改 4: shimmer 动画改用 GPU 合成属性

**文件:** `frontend/src/styles/markdown-content.css`

```css
/* 修改前 */
@keyframes img-shimmer {
  to { background-position: -200% 0; }
}

/* 修改后 */
.markdown-content img[data-loaded="0"]:not([src=""]) {
  will-change: transform;
}
@keyframes img-shimmer {
  to { transform: translateX(-200%); }
}
```

使用 `transform` 代替 `background-position` 驱动动画。
`transform` 变化可由 GPU 在合成层直接处理，不占用主线程。
同时对加载中的图片添加 `will-change: transform` 提示浏览器提前创建合成层。

注意: shimmer 的视觉效果实现方式需要配合调整，
可能需要改为在伪元素上做 transform 位移来模拟 shimmer 效果。

### 修改 5: 减小 IntersectionObserver 预加载距离

**文件:** `frontend/src/components/reader/markdown-viewer.tsx`

```typescript
// 修改前
{ root: null, rootMargin: "600px 0px" }

// 修改后
{ root: null, rootMargin: "200px 0px" }
```

将预加载触发距离从 600px 减至 200px。
200px 在正常滚动速度下仍能保证内容提前加载完毕，
同时大幅减少快速滚动时的管线处理压力。

### 修改 6（可选）: 图片事件处理改为 React 管理

**文件:** `frontend/src/components/reader/markdown-pipeline.ts`

此项改动较大，且当前内联 JS 的性能影响相对较小。
可作为后续优化考虑，将 onerror/onload 改为在 MarkdownViewer 挂载后通过
事件委托统一管理，避免内联脚本执行。

## 对架构的影响

- 修改 1-3 为局部优化，不涉及组件接口变化，不影响其他模块
- 修改 2 需要 `useTextSelection` hook 的函数签名增加一个可选参数，
  调用方需传入容器 ref（已在 document-reader.tsx 中存在）
- 修改 4 为纯 CSS 改动，无接口影响
- 修改 5 可能影响用户感知的"内容出现时机"，需实际测试确认 200px 是否足够

## 验证方法

1. 打开包含大量内容和图片的文档
2. 使用 Chrome DevTools Performance 面板录制滚动过程
3. 对比修改前后的帧率（FPS）、主线程长任务数量
4. 确认选中文字弹出菜单的位置计算在内部容器滚动时仍然正确
