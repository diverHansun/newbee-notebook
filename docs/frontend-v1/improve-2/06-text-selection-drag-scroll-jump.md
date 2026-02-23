# P7: 文字选中拖动超出视口时选区跳转

---

## 1. 当前问题

### 1.1 现象

在 Markdown 查看器中，使用鼠标拖拽选中文字时：

1. **在视口内拖动**：蓝色选区跟随鼠标正常延伸，表现正常
2. **拖动到视口底部边缘继续向下**：浏览器触发 autoscroll（自动滚动），此时选区突然：
   - 跳回到上方（之前未被选中的文字被选中）
   - 用户松开鼠标后，选区不是用户期望的范围

### 1.2 关键背景：浏览器 autoscroll 机制

当鼠标按住拖动到视口边缘时，浏览器会自动滚动页面（autoscroll）。在此过程中：

- **不触发新的 `mousedown` 事件**（按键没有重新按下）
- **`selectionchange` 事件持续触发**（选区随页面滚动而变化）
- **anchorNode / focusNode 位置关系在 DOM 中动态变化**

### 1.3 当前实现分析

`useTextSelection.ts` 的当前实现（improve-2 已更新版）：

```
handleMouseDown：
  - 标记 isSelectingRef = true
  - 标记 startedInContainerRef = true（若在容器内）
  - 调用 clearSelectionUi()

handleSelectionChange：
  - isSelectingRef.current 为 true 时直接 return（不显示菜单）

handleMouseUp：
  - 检查 shouldFinalizeSelection
  - 重置两个 ref
  - 调用 showMenuFromCurrentSelection()
```

**improve-2 的 mouseup 门控解决了"菜单提前弹出"问题，但不能解决选区本身的跳转**。`clearSelectionUi()` 和 `showMenuFromCurrentSelection()` 操作的是 Zustand 的 React 状态，不控制浏览器的原生选区。原生选区跳转由 DOM 结构变化引起，与 React 状态无关。

### 1.4 根本原因：IntersectionObserver 触发 DOM 变更与 autoscroll 竞争

问题的核心由两个机制叠加造成：

**机制A：autoscroll 触发 IntersectionObserver**

```
用户向下拖动到视口底部
  -> 浏览器 autoscroll 开始滚动页面
  -> sentinel 元素（"正在加载更多内容..."）进入视口
  -> IntersectionObserver 触发
  -> setVisibleChunkCount(prev => prev + CHUNK_LOAD_STEP)
  -> React re-render：新的 <section> 元素追加到 DOM
```

**机制B：DOM 追加影响原生选区**

```
新 <section> 元素追加到 DOM
  -> 若用户选区的 focusNode 位于新追加的内容区域之前
     （即 focus 点在文档中的相对位置被新内容推移）
  -> 浏览器更新 anchorNode/focusNode 的 DOM 位置
  -> 部分浏览器实现（尤其 Chromium）会重新计算选区
  -> 选区方向可能突变（正向变反向，或 focus 重定位）
  -> 蓝色高亮区域跳转到新位置
```

**竞争条件时序图**：

```
T+0ms    mousedown in container, isSelectingRef = true
T+100ms  用户拖到视口底部，autoscroll 启动
T+200ms  sentinel 进入视口，IntersectionObserver fires
T+210ms  setVisibleChunkCount(3 -> 4)
T+215ms  React re-render，<section key="chunk-doc-3"> 插入 DOM
T+220ms  浏览器重新计算选区，focusNode 位置更新
T+230ms  原生选区跳转，蓝色高亮重定位
T+500ms  用户松开鼠标（mouseup）
T+502ms  showMenuFromCurrentSelection() 读取已发生跳转的选区
T+505ms  菜单出现在错误位置，或选中文字不是用户期望的内容
```

### 1.5 为什么看起来选区"跳到上方"

新 `<section>` 被追加时，focusNode 的 DOM 树位置发生变化。浏览器在某些情况下将 focus 重置到最近的稳定节点，而最近的稳定节点可能是选区起始附近的文字，导致用户看到选区从下方"跳回"到上方。

---

## 2. 解决方案

### 核心思路

**活跃选择期间，冻结新块的加载**。防止 DOM 结构在用户拖拽过程中发生变化，从根本上消除竞争条件。

### 2.1 在 reader-store 中新增 isSelecting 状态

`reader-store.ts` 目前仅管理 selection 和菜单显示状态。新增 `isSelecting` 布尔字段：

```typescript
// 修改 stores/reader-store.ts
type ReaderState = {
  // ... 现有字段 ...
  isSelecting: boolean;
  setIsSelecting: (value: boolean) => void;
};

// 初始值
isSelecting: false,
setIsSelecting: (value) => set({ isSelecting: value }),
```

### 2.2 useTextSelection 中设置 isSelecting 状态

在 `useTextSelection.ts` 的 `handleMouseDown` 和 `handleMouseUp` 中同步 store：

```typescript
const { setSelection, showMenu, hideMenu, setIsSelecting } = useReaderStore();

const handleMouseDown = (event: MouseEvent) => {
  if (isTargetInsideSelectionMenu(event.target)) return;
  const startedInContainer = isTargetInsideContainer(event.target);
  startedInContainerRef.current = startedInContainer;
  isSelectingRef.current = startedInContainer;
  if (startedInContainer) {
    setIsSelecting(true);  // 新增：进入选择状态，通知 MarkdownViewer 冻结加载
  }
  clearSelectionUi();
};

const handleMouseUp = () => {
  const shouldFinalizeSelection = startedInContainerRef.current || isSelectingRef.current;
  isSelectingRef.current = false;
  startedInContainerRef.current = false;
  setIsSelecting(false);  // 新增：退出选择状态，解除 MarkdownViewer 冻结
  if (!shouldFinalizeSelection) return;
  showMenuFromCurrentSelection();
};
```

### 2.3 MarkdownViewer 中读取 isSelecting，冻结 IntersectionObserver

在 `markdown-viewer.tsx` 中从 store 读取 `isSelecting`，在 IntersectionObserver 回调中检查此标志：

```typescript
import { useReaderStore } from "@/stores/reader-store";

export function MarkdownViewer({ content, documentId, className, containerRef }: MarkdownViewerProps) {
  const isSelecting = useReaderStore((state) => state.isSelecting);
  // ...

  useEffect(() => {
    if (!hasMoreChunks) return;
    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        if (isSelecting) return;  // 新增：用户正在拖选，冻结加载
        setVisibleChunkCount((prev) => Math.min(prev + CHUNK_LOAD_STEP, chunks.length));
      },
      { root: null, rootMargin }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [chunks.length, hasMoreChunks, rootMargin, isSelecting]);  // 新增 isSelecting 依赖
```

### 2.4 mouseup 之后解冻并继续加载

当 `isSelecting` 从 `true` 变为 `false` 时（mouseup 触发），IntersectionObserver 所在的 useEffect 会因依赖变化重新执行，重新创建 observer，自然地恢复对 sentinel 的监测。若 sentinel 此时还在视口内（autoscroll 后），新的 observer 会立即触发，加载被冻结期间未加载的块。

### 2.5 补充：增大预加载距离减少冻结影响

配合 P6 中的 `MIN_ROOT_MARGIN_PX = 900` 和 `CHUNK_LOAD_STEP = 2`，大多数情况下接近 sentinel 之前内容已预加载完成，用户拖到视口底部时根本不会触发新块加载，冻结机制属于兜底保护。

---

## 3. 架构影响与修改点

### 修改文件

**`frontend/src/stores/reader-store.ts`**

| 变更 | 说明 |
|------|------|
| 新增 `isSelecting: boolean` 字段 | 用于跨组件传递选择状态 |
| 新增 `setIsSelecting` action | 由 useTextSelection 调用 |

**`frontend/src/lib/hooks/useTextSelection.ts`**

| 变更 | 位置 | 说明 |
|------|------|------|
| 引入 `setIsSelecting` | `useReaderStore` 解构 | 新增字段 |
| `handleMouseDown` 中调用 `setIsSelecting(true)` | startedInContainer 分支 | 仅容器内选择时才标记 |
| `handleMouseUp` 中调用 `setIsSelecting(false)` | ref 重置后 | 任何 mouseup 都解除冻结 |

**`frontend/src/components/reader/markdown-viewer.tsx`**

| 变更 | 位置 | 说明 |
|------|------|------|
| 引入 `useReaderStore` 读取 `isSelecting` | 组件顶部 | Zustand selector，只订阅该字段 |
| IntersectionObserver 回调中加 `if (isSelecting) return` | 第 107-115 行 | 冻结加载 |
| `useEffect` 依赖数组加 `isSelecting` | 第 116 行 | mouseup 后自动恢复监测 |

### 非修改文件

- `selection-menu.tsx`：不变
- `document-reader.tsx`：不变
- `chat-panel.tsx`：不变

### 状态流向

```
useTextSelection
  mousedown(container) -> setIsSelecting(true) -> reader-store
                                                        |
                                                        -> MarkdownViewer reads isSelecting
                                                        -> IntersectionObserver callback skips load
  mouseup          -> setIsSelecting(false) -> reader-store
                                                        |
                                                        -> useEffect re-runs
                                                        -> observer re-created, resumes loading
```

### 行为变化对比

| 场景 | 修改前 | 修改后 |
|------|--------|--------|
| 视口内拖选 | 正常 | 不变 |
| 拖到视口底部触发 autoscroll | 选区跳转 | 新块加载被冻结，选区稳定 |
| autoscroll 后松开鼠标 | 选区位置不确定 | 选区准确，菜单出现在正确位置 |
| 松开后继续加载未显示内容 | 自然触发 IntersectionObserver | mouseup 解冻后 observer 重建，自然触发 |

### 注意事项

- `isSelecting` 是选择性订阅（`useReaderStore((state) => state.isSelecting)`），只有 `MarkdownViewer` 订阅此字段，不会导致无关组件 re-render
- 若用户触发 autoscroll 但没有拖入足够触发 sentinel 的区域，此机制完全透明，无副作用
- 极端场景：若冻结期间 sentinel 在视口外（autoscroll 已到达），mouseup 解冻后 observer 检测到 sentinel 不在视口内，不会立即加载，等下次滚动时自然触发，此为正确行为
