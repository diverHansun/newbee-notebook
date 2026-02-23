# P6: Markdown 查看器滚动性能优化

---

## 1. 当前问题

### 1.1 现象

在 Markdown 查看器（`components/reader/markdown-viewer.tsx`）中滚动时，出现明显卡顿，表现为：
- 快速滚动时内容加载出现短暂停顿
- 滚动时帧率下降，视觉上有跳跃感

### 1.2 现有架构

当前实现已包含部分优化措施：

| 优化手段 | 实现位置 | 说明 |
|----------|----------|------|
| 分块渲染 | `splitMarkdownIntoChunks()`（第 20-54 行） | 大于 120KB 的文档按 24KB 分块 |
| 按需加载 | `IntersectionObserver`（第 107-115 行） | 接近底部时加载下一块 |
| HTML 缓存 | `htmlCacheRef`（第 84、118-132 行） | 避免重复调用 `renderMarkdownToHtml` |
| CSS 渲染优化 | `content-visibility: auto`（markdown-content.css） | 减少屏幕外内容的绘制开销 |

### 1.3 性能瓶颈分析

**瓶颈一：`CHUNK_LOAD_STEP = 1`，每次只加载 1 块（第 9 行）**

`IntersectionObserver` 的回调每次仅触发 `setVisibleChunkCount(prev => prev + 1)`。在快速滚动时，用户到达 sentinel 元素（加载提示）时，只新增 1 个 24KB 的块。若用户继续快速滚动，sentinel 需要再次进入视口才能加载下一块，导致可见区域出现"加载中"提示的闪烁。

**瓶颈二：`MIN_ROOT_MARGIN_PX = 360px` 预加载距离不足（第 10 行）**

`rootMargin: "360px 0px"` 意味着 sentinel 元素在距视口底部 360px 时才触发加载。对于快速滚动，360px 不足以在内容到达视口前完成渲染。

**瓶颈三：`htmlChunks` useMemo 每次 visibleChunkCount 变化都重建数组（第 118-132 行）**

```typescript
const htmlChunks = useMemo(() => {
  const output: string[] = [];
  for (let idx = 0; idx < visibleChunkCount; idx += 1) {
    // 所有已加载的块都被遍历
    const html = cache.get(idx) || renderMarkdownToHtml(...);
    output.push(html);
  }
  return output;
}, [chunks, documentId, visibleChunkCount]);
```

虽然 `renderMarkdownToHtml` 有缓存，但数组的重新分配（`output = []`）和遍历操作本身在大文档下有开销。每加载一个新块，之前所有块的 HTML 字符串都经历数组重构。

**瓶颈四：`key={idx}` 数组索引作为 key（第 137 行）**

```typescript
{htmlChunks.map((html, idx) => (
  <section key={idx} className="markdown-chunk" ... />
))}
```

虽然在此场景（单调递增、仅追加）中不直接导致 DOM 复用错误，但 React 的 diffing 无法利用稳定 key 做优化，当新块加载时整个列表中现有块也会参与 reconciliation。

**瓶颈五：组件没有 React.memo 包裹（第 81 行）**

`MarkdownViewer` 是无 memo 的函数组件，任何父组件的 re-render 都会导致它重新执行，即使 `content`、`documentId`、`className` 均未变化。

---

## 2. 解决方案

### 2.1 提升预加载距离（低风险，效果显著）

将 `MIN_ROOT_MARGIN_PX` 从 360 提升至 900，`CHUNK_LOAD_STEP` 从 1 提升至 2：

```typescript
// 修改前
const MIN_ROOT_MARGIN_PX = 360;
const CHUNK_LOAD_STEP = 1;

// 修改后
const MIN_ROOT_MARGIN_PX = 900;
const CHUNK_LOAD_STEP = 2;
```

效果：在用户接近底部 900px 时开始加载，每次加载 2 块（约 48KB），为快速滚动提供足够缓冲。

### 2.2 稳定 key（低风险，工程规范）

```typescript
// 修改前
<section key={idx} ... />

// 修改后
<section key={`chunk-${documentId ?? "doc"}-${idx}`} ... />
```

### 2.3 React.memo 包裹（低风险）

```typescript
// 修改前
export function MarkdownViewer({ content, documentId, className, containerRef }: MarkdownViewerProps) {

// 修改后
export const MarkdownViewer = React.memo(function MarkdownViewer({
  content, documentId, className, containerRef
}: MarkdownViewerProps) {
  // ...
});
```

所有 props 均为原始类型（string、RefObject），memo 的浅比较可有效避免父组件无关 re-render 触发 MarkdownViewer 重新执行。

### 2.4 htmlChunks 仅追加新块（中等复杂度，优化幅度大）

将 `htmlChunks` 的 useMemo 改为仅在 `visibleChunkCount` 增加时才追加新元素，而不是遍历全部：

```typescript
// 思路：用 useRef 保存已渲染的 section 列表，visibleChunkCount 增加时只追加
const renderedSectionsRef = useRef<React.ReactNode[]>([]);

// 在 render 时，仅渲染 renderedSectionsRef.current.length 到 visibleChunkCount 范围的新 section
// 已有 section 复用，不重建
```

具体实现：将 `<section>` 节点对象缓存在 ref 中，每次 visibleChunkCount 增加时 push 新节点，render 时直接展示 ref 数组。

此方案绕开了 useMemo 的数组重建问题。

---

## 3. 架构影响与修改点

### 修改文件

**`frontend/src/components/reader/markdown-viewer.tsx`**

| 变更 | 行 | 说明 |
|------|-----|------|
| `MIN_ROOT_MARGIN_PX` 从 360 改为 900 | 第 10 行 | 提前加载触发距离 |
| `CHUNK_LOAD_STEP` 从 1 改为 2 | 第 9 行 | 每次加载 2 块 |
| 添加 `React.memo` 包裹 | 第 81 行 | 避免父组件无关 re-render |
| `key={idx}` 改为稳定 key | 第 137 行 | React diff 优化 |

### 非修改文件

- `markdown-pipeline.ts`：渲染逻辑不变
- `markdown-content.css`：`content-visibility` 保留
- `document-reader.tsx`：不变

### 优先级建议

建议按以下顺序实施，每步可单独验证效果：

1. `CHUNK_LOAD_STEP = 2` + `MIN_ROOT_MARGIN_PX = 900`（1 行改动，效果最直接）
2. React.memo 包裹（3 行改动）
3. 稳定 key（1 行改动）
4. htmlChunks 追加优化（中等复杂度，只在 1、2、3 不够时做）

### 验收标准

- 快速滚动时，`正在加载更多内容...` 提示不出现或出现时间极短（< 100ms）
- `Performance` 面板中滚动时无长任务（> 50ms 的任务）
- 父组件重渲染（如会话列表更新）不导致 MarkdownViewer 重新执行
