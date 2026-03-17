# Markdown Viewer 书签集成

## 1. 设计目标

在 Markdown Viewer 的文本选择流程中加入书签创建能力，并以边距图标的方式展示已有书签，点击图标可联动 Studio Panel。

核心约束：
- 不修改 `useTextSelection` hook 的接口签名
- 不修改 `renderMarkdownToHtml` 渲染管道
- 书签创建与现有的 Explain/Conclude 操作在 UI 上明确区分

## 2. 书签创建流程

### 2.1 SelectionMenu 扩展

在现有 `SelectionMenu` 组件中新增书签按钮，与 Explain/Conclude 按钮通过视觉分隔线区分。

```
现有按钮          分隔线   新增按钮
[解释] [总结]       |     [书签]
  AI 操作                本地存储操作
```

组件接口变更：

```typescript
type SelectionMenuProps = {
  onExplain: (payload: { documentId: string; selectedText: string }) => void;
  onConclude: (payload: { documentId: string; selectedText: string }) => void;
  onMark: (payload: { documentId: string; selectedText: string }) => void;  // 新增
};
```

书签按钮点击后立即 `hideMenu()`，不进入 chat 流程，直接调用 `onMark` 回调。

### 2.2 char_offset 计算

`onMark` 回调在 `DocumentReader` 中实现，负责计算 `anchor_text` 和 `char_offset`。

计算步骤：

1. `anchor_text` = `selection.selectedText`（来自 `useReaderStore`）
2. 通过 `window.getSelection().getRangeAt(0).startContainer` 向上查找最近的 chunk 容器 div
3. 从 chunk div 的 `data-chunk-index` 属性获取 chunk 索引
4. 在该 chunk 的 raw markdown 文本中搜索 `anchor_text` 首次出现的位置
5. `char_offset = chunk.startChar + positionWithinChunk`

```typescript
const onMark = useCallback(
  async ({ documentId, selectedText }: { documentId: string; selectedText: string }) => {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;

    const range = selection.getRangeAt(0);
    const chunkEl = (range.startContainer instanceof Element
      ? range.startContainer
      : range.startContainer.parentElement
    )?.closest("[data-chunk-index]");

    const chunkIndex = Number(chunkEl?.getAttribute("data-chunk-index") ?? 0);
    const chunk = chunks[chunkIndex];
    if (!chunk) return;

    const posInChunk = chunk.content.indexOf(selectedText);
    const charOffset = chunk.startChar + Math.max(0, posInChunk);

    await createMark({
      document_id: documentId,
      anchor_text: selectedText,
      char_offset: charOffset,
    });
  },
  [chunks, createMark]
);
```

### 2.3 MarkdownViewer chunk 标记

MarkdownViewer 渲染每个 chunk 时，在 chunk 容器 `<section>` 元素上添加 `data-chunk-index` 属性（当前渲染为 `<section class="markdown-chunk">`）：

```tsx
<section key={chunkIndex} className="markdown-chunk" data-chunk-index={chunkIndex}>
  {/* chunk rendered HTML */}
</section>
```

此属性仅用于书签创建时定位 chunk，不影响现有渲染逻辑。

注意：当前 `splitMarkdownIntoChunks` 返回 `string[]`，无法直接获取 `startChar`。实现时需新增一个辅助函数 `computeChunkOffsets(content: string, chunks: string[]): ChunkMeta[]`，返回每个 chunk 在原始 markdown 中的起始偏移量：

```typescript
type ChunkMeta = { content: string; startChar: number };

function computeChunkOffsets(fullContent: string, chunks: string[]): ChunkMeta[] {
  let offset = 0;
  return chunks.map((chunk) => {
    const start = fullContent.indexOf(chunk, offset);
    const meta = { content: chunk, startChar: start >= 0 ? start : offset };
    offset = meta.startChar + chunk.length;
    return meta;
  });
}
```

此函数在 DocumentReader 中调用一次（`useMemo`），结果传递给 `onMark` handler 和 `applyMarkIcons`。不修改 `splitMarkdownIntoChunks` 的返回类型，避免破坏现有 MarkdownViewer 接口。

### 2.4 API 调用

创建书签调用后端 REST API（document_id 在 URL 路径中）：

```
POST /api/v1/documents/{document_id}/marks
{
  "anchor_text": "选中的文本内容",
  "char_offset": 12345
}
```

使用 TanStack Query 的 `useMutation`，成功后通过 `queryClient.invalidateQueries` 刷新当前文档的 marks 列表。

创建失败时（如文档状态不支持、网络错误），显示 toast 提示（使用 `marks.bookmarkCreateFailed` i18n 字符串）。

## 3. 书签边距图标展示

### 3.1 设计方案：DOM 后处理

不修改 rehype 渲染管道。在每个 chunk 挂载到 DOM 后，通过 `useEffect` 对已渲染的 HTML 进行后处理，注入边距图标。

选择此方案的理由：
- MarkdownViewer 使用 `dangerouslySetInnerHTML`，React 不管理 chunk 内部 DOM，因此直接操作是安全的
- 避免修改 unified/remark/rehype 管道，降低复杂度
- 图标是纯展示层，与 markdown 内容解耦

### 3.2 数据加载

通过 TanStack Query 加载当前文档的书签：

```typescript
const marksQuery = useQuery({
  queryKey: ["marks", documentId],
  queryFn: () => listMarks({ document_id: documentId }),
  enabled: Boolean(documentId),
});
```

### 3.3 图标注入流程

新增工具函数 `applyMarkIcons`：

```typescript
function applyMarkIcons(
  chunkEl: HTMLElement,
  marks: Mark[],
  chunkStartChar: number,
  chunkEndChar: number
): void
```

执行步骤：

1. 清理该 chunk 中已有的 mark 图标（防止重复）
2. 筛选 `char_offset` 落在 `[chunkStartChar, chunkEndChar)` 范围内的 marks
3. 对每个 mark，使用 `TreeWalker` 遍历 chunk 内文本节点，查找包含 `anchor_text` 的节点
4. 找到后，取该文本节点最近的块级祖先元素（`p`、`li`、`h1-h6`、`blockquote`）
5. 在该块级元素上设置 `data-mark-ids` 属性（多个 mark 用逗号分隔）
6. CSS 通过 `[data-mark-ids]` 选择器显示图标

### 3.4 useEffect 调用时机

在 MarkdownViewer 中，每个 chunk 渲染后执行：

```typescript
useEffect(() => {
  if (!marks || marks.length === 0) return;
  chunks.forEach((chunk, index) => {
    const chunkEl = containerRef.current?.querySelector(
      `[data-chunk-index="${index}"]`
    );
    if (chunkEl instanceof HTMLElement) {
      applyMarkIcons(chunkEl, marks, chunk.startChar, chunk.startChar + chunk.content.length);
    }
  });
}, [marks, chunks, visibleChunkCount]);
```

依赖项包含 `visibleChunkCount`，确保懒加载新 chunk 时也会执行图标注入。

### 3.5 CSS 样式

MarkdownViewer 容器左侧预留 24px padding 供图标使用：

```css
.markdown-viewer-content {
  padding-left: 24px;
  position: relative;
}

[data-mark-ids] {
  position: relative;
}

[data-mark-ids]::before {
  content: "";
  position: absolute;
  left: -20px;
  top: 4px;
  width: 14px;
  height: 14px;
  background-image: url("bookmark-icon.svg");
  background-size: contain;
  cursor: pointer;
  opacity: 0.6;
  transition: opacity 0.15s ease;
}

[data-mark-ids]:hover::before {
  opacity: 1;
}
```

Hover 时通过 Tooltip 显示 `anchor_text` 前 40 个字符。Tooltip 可复用现有的 CSS overlay 模式或使用简单的 `title` 属性实现 v1。

## 4. 跨面板联动

### 4.1 Reader -> Studio 联动

点击边距书签图标时的交互：

1. 在 MarkdownViewer 容器上通过事件代理监听 `click` 事件
2. 检测 `event.target.closest("[data-mark-ids]")` 或点击目标是 `::before` 伪元素对应的区域
3. 从 `data-mark-ids` 属性提取 mark ID
4. 更新 `studioStore.activeMarkId`
5. Studio Panel 响应 `activeMarkId` 变化，切换到 Marks 视图并高亮该 mark

由于 CSS `::before` 伪元素不可直接绑定事件，实际方案为在块级元素左侧 padding 区域的点击判断：

```typescript
const handleClick = (event: MouseEvent) => {
  const target = event.target as HTMLElement;
  const markEl = target.closest("[data-mark-ids]");
  if (!markEl) return;

  // 判断点击是否在左侧 padding 区域（图标区域）
  const rect = markEl.getBoundingClientRect();
  const paddingLeft = 24; // 与 CSS 中 markdown-viewer-content 的 padding-left 一致
  if (event.clientX > rect.left + paddingLeft) return; // 点击在内容区域，忽略

  const markIds = markEl.getAttribute("data-mark-ids");
  if (markIds) {
    studioStore.setActiveMarkId(markIds.split(",")[0]);
  }
};
```

### 4.2 Studio -> Reader 联动

从 Studio 点击 mark 项时，反向导航到 Reader：

1. 如果对应文档已在 Reader 中打开，滚动到 mark 所在位置
2. 如果未打开，先切换到 reader 视图、打开该文档，待内容加载后滚动到位置

滚动定位方式：在已渲染的 DOM 中查找 `[data-mark-ids]` 包含目标 mark ID 的元素，调用 `scrollIntoView({ behavior: "smooth", block: "center" })`。

## 5. 与后端 API 的对应关系

| 前端操作 | 后端 API | 说明 |
|---------|---------|------|
| 创建书签 | POST /api/v1/documents/{document_id}/marks | 选中文本后点击书签按钮 |
| 加载文档书签 | GET /api/v1/documents/{document_id}/marks | 打开文档时加载（Reader 用） |
| 加载 Notebook 书签 | GET /api/v1/notebooks/{notebook_id}/marks | Studio Marks 列表用 |
| 删除书签 | DELETE /api/v1/marks/{mark_id} | Studio Marks 视图中操作（后续批次） |
