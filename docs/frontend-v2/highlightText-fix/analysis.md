# 书签高亮与跳转问题：分析与修复方案

## 背景

用户反馈以下两类问题：

1. 拖拽选中文本并点击"书签"按钮后，文档内的黄色高亮有时不显示，或显示有延迟。
2. 在右侧 Studio 面板点击书签条目后，未能成功跳转到对应文档的对应位置，高亮时显示时不显示。

---

## 涉及文件

| 文件 | 作用 |
|------|------|
| `frontend/src/components/reader/document-reader.tsx` | 书签创建、高亮渲染、滚动定位的核心逻辑 |
| `frontend/src/stores/reader-store.ts` | 全局状态：`activeMarkId`、`markScrollTrigger`（待增加） |
| `frontend/src/components/studio/studio-panel.tsx` | 右侧面板书签列表，点击触发跳转 |
| `frontend/src/lib/reader/chunk-marks.ts` | chunk 偏移量计算辅助函数 |

---

## 问题一：`highlightTextInChunk` 跨元素边界失败

### 现象

高亮不显示，或仅偶尔显示。

### 根本原因

函数位于 `document-reader.tsx` 第 533—587 行，存在两处设计缺陷：

**缺陷 A：搜索文本截断为前 30 字符**

```typescript
const searchSnippet = anchorText.slice(0, 30).trim();
```

只取前 30 个字符作为搜索片段。这意味着：
- 如果书签内容的前 30 字符在某个 text node 内存在，会命中错误位置（误匹配）。
- 对于在渲染后文本节点中分布不均的内容，前 30 字符可能恰好跨越了 `<strong>`、`<em>`、`<code>` 等元素的边界，导致在任何单个 text node 内都找不到，直接返回 `null`。

**缺陷 B：`range.surroundContents()` 在跨元素边界时抛出异常**

```typescript
range.surroundContents(markEl);
```

W3C 规范明确规定：当 Range 的 startContainer 或 endContainer 不是同一个祖先元素，或 Range 跨越了元素边界时，`surroundContents()` 抛出 `HierarchyRequestError`。

例如，用户选中了 "这是**粗体**内容" 这样跨越普通文本和 `<strong>` 的片段，调用 `surroundContents` 会抛异常，catch 块直接返回 `null`，高亮完全不显示。

**结论**：Markdown 文档经过渲染后，包含大量 `<strong>`、`<em>`、`<code>`、`<a>` 等行内元素，用户选中的文本跨越这些元素边界的概率极高。当前实现在绝大多数真实场景下都会失败。

### 修复方案

重写 `highlightTextInChunk`，采用"收集全部文本节点 → 拼接全文 → 全量匹配 → 逐节点分段包裹"的策略：

**第一步：收集所有文本节点并记录偏移**

```
nodes = []
cumOffset = 0
用 TreeWalker 遍历 chunkEl 下所有 TEXT 节点：
    nodes.push({ node, start: cumOffset, end: cumOffset + node.length })
    cumOffset += node.length
concatenated = 拼接所有 text node 的内容
```

**第二步：在拼接文本中全量搜索 anchorText（空白字符折叠归一化）**

`window.getSelection().toString()` 在选取跨段落/跨表格单元格文本时，会将换行符 `\n` 转为空格，并且在段落边界处产生多余空格（如 `"safety.  In"` vs DOM 中的 `"safety.\nIn"`）。简单的逐字符替换 `s.replace(/\s/g, ' ')` 无法处理这种长度不一致的情况。

因此采用 `collapseWs`：将连续空白字符折叠为单个空格，同时维护位置映射数组 `origIndices`，记录折叠后每个字符在原始字符串中的位置：

```
collapseWs = (s) =>
    chars = [], indices = []
    prevSpace = false
    for i in 0..s.length:
        isSpace = /\s/.test(s[i])
        if isSpace:
            if !prevSpace: chars.push(' '), indices.push(i)
            prevSpace = true
        else:
            chars.push(s[i]), indices.push(i)
            prevSpace = false
    return { collapsed: chars.join(''), origIndices: indices }

{ collapsed: collapsedConcat, origIndices } = collapseWs(concatenated)
{ collapsed: collapsedAnchor } = collapseWs(anchorText)
collapsedMatchStart = collapsedConcat.indexOf(collapsedAnchor)
if collapsedMatchStart === -1: return null
collapsedMatchEnd = collapsedMatchStart + collapsedAnchor.length

// 通过 origIndices 映射回原始拼接文本中的偏移
matchStart = origIndices[collapsedMatchStart]
matchEnd = collapsedMatchEnd < origIndices.length
    ? origIndices[collapsedMatchEnd]
    : concatenated.length
```

`collapseWs` 确保无论 DOM 中是 `\n` 还是多个空格，与 `Selection.toString()` 产生的单空格都能正确匹配，同时通过 `origIndices` 保证后续步骤使用准确的原始偏移量。

**第三步：对每个与匹配区间有交集的文本节点，拆分并包裹**

```
createdMarks = []
for each node in nodes:
    if node.end <= matchStart || node.start >= matchEnd: continue

    localStart = max(matchStart, node.start) - node.start
    localEnd   = min(matchEnd,   node.end)   - node.start

    // splitText 在指定偏移处将 text node 一分为二，返回后半段
    // 包裹中间段，并记录 <mark> 元素用于 cleanup
    targetNode = node.node
    if localStart > 0:
        targetNode = targetNode.splitText(localStart)
        // 此时 targetNode 是从 localStart 开始的后半段
    if localEnd - localStart < targetNode.length:
        targetNode.splitText(localEnd - localStart)
        // 此时 targetNode 只包含要高亮的文字

    markEl = document.createElement('mark')
    markEl.className = 'mark-text-highlight'
    targetNode.parentNode.insertBefore(markEl, targetNode)
    markEl.appendChild(targetNode)
    createdMarks.push(markEl)
```

**第四步：cleanup 时移除所有 `<mark>` 元素并 normalize**

```
cleanup = () =>
    for each markEl in createdMarks:
        parent = markEl.parentNode
        while markEl.firstChild: parent.insertBefore(markEl.firstChild, markEl)
        parent.removeChild(markEl)
    chunkEl.normalize()
```

**第五步：scrollIntoView 以第一个 `<mark>` 为基准**

```
scrollIntoView = (container) =>
    使用 createdMarks[0].getBoundingClientRect() 计算滚动偏移
```

---

## 问题二：点击同一书签第二次不响应

### 现象

文档已打开，当前书签已处于激活状态。再次点击同一书签条目，页面没有任何反应。

### 根本原因

scroll-to-mark effect 的依赖项数组：

```typescript
useEffect(() => {
  // ...
}, [activeMarkId, chunkOffsets, marksQuery.data?.marks, totalChunkCount, visibleChunkCount]);
```

当用户点击 studio-panel 中的同一书签时（第 533—535 行）：

```typescript
onClick={() => {
  setActiveMarkId(mark.mark_id);      // activeMarkId 值不变，state 不更新
  onOpenDocument(mark.document_id, mark.mark_id);  // 已在该文档，currentDocumentId 不变
}}
```

`activeMarkId` 的值从 `"abc"` 被设置为 `"abc"`，Zustand 检测到值相同，不触发 re-render，effect 也不重新执行。用户看到的是点击无效。

### 修复方案

在 `reader-store.ts` 中新增 `markScrollTrigger: number` 字段，每次调用 `setActiveMarkId` 传入非 null 值时自增：

```typescript
// reader-store.ts
type ReaderState = {
  // ...
  markScrollTrigger: number;   // 新增
};

setActiveMarkId: (markId) =>
  set((state) => ({
    activeMarkId: markId,
    markScrollTrigger: markId != null
      ? state.markScrollTrigger + 1
      : state.markScrollTrigger,
  })),
```

在 `document-reader.tsx` 中将 `markScrollTrigger` 加入 effect 依赖：

```typescript
const markScrollTrigger = useReaderStore((state) => state.markScrollTrigger);

useEffect(() => {
  // ...
}, [activeMarkId, markScrollTrigger, chunkOffsets, marksQuery.data?.marks, totalChunkCount, visibleChunkCount]);
```

这样每次点击书签，无论 markId 是否变化，`markScrollTrigger` 都会自增，确保 effect 重新执行。

---

## 问题三：新建书签后高亮出现延迟

### 现象

用户选中文本，点击书签按钮，书签图标出现在文档左侧，但黄色高亮不立即显示，需要等一段时间后才出现（或不出现）。

### 根本原因

`handleMark` 执行流程（第 179—211 行）：

```typescript
const mark = await createMarkMutation.mutateAsync({...});
setReaderActiveMarkId(mark.mark_id);   // 1. 立即设置 activeMarkId
// onSuccess 中：
void queryClient.invalidateQueries({...});  // 2. 异步触发 marks 查询重新请求
```

scroll-to-mark effect 在步骤 1 执行后立即触发，但此时：

```typescript
const targetMark = marksQuery.data.marks.find((item) => item.mark_id === activeMarkId);
if (!targetMark) return;   // 新 mark 尚未在缓存中，直接 return
```

由于 `queryClient.invalidateQueries` 是异步的，新书签数据尚未加入 React Query 缓存，effect 找不到 target mark 并提前返回。待缓存更新后，effect 因 `marksQuery.data?.marks` 变化而重新触发，高亮才出现——这就是用户感知到的"延迟"。

### 修复方案

在 `handleMark` 中，将 mutate 返回的 mark 数据在 query 缓存更新完成后再设置 activeMarkId，利用 `await queryClient.invalidateQueries` 的 Promise 等待缓存刷新：

```typescript
const mark = await createMarkMutation.mutateAsync({...});

// 等待 query 缓存刷新完成后再激活，避免 effect 因 mark 不在缓存中而提前 return
await queryClient.invalidateQueries({ queryKey: ["marks", "document", documentId] });
await queryClient.invalidateQueries({ queryKey: ["marks", "notebook"] });

setReaderActiveMarkId(mark.mark_id);
setStudioActiveMarkId(mark.mark_id);
```

注意：`queryClient.invalidateQueries` 返回一个 Promise，await 它会等到对应 query 重新 fetch 并将数据写入缓存后 resolve。这样 effect 触发时 mark 已在缓存中，不再出现提前 return。

---

## 修复优先级与影响范围

| 问题 | 文件 | 改动量 | 优先级 | 预期效果 |
|------|------|--------|--------|----------|
| 跨元素高亮失败（问题一） | `document-reader.tsx` | 中（重写一个纯函数） | P0 | 修复绝大多数高亮不显示的情况 |
| 重复点击不响应（问题二） | `reader-store.ts` + `document-reader.tsx` | 小 | P1 | 修复重复点击同书签无效的问题 |
| 新建书签高亮延迟（问题三） | `document-reader.tsx` | 小（2 行改动） | P1 | 新建书签后高亮即时显示 |

---

## 不在本次修复范围内

- 书签 `char_offset` 的计算精度问题（`handleMark` 中使用 `chunk.content.indexOf(selectedText)`，存在文本重复时定位到错误位置）。
- 书签在文档更新后的失效处理（文档内容变更后 `char_offset` 对应位置漂移）。

这两个问题独立于高亮渲染逻辑，可作为后续专项优化。
