# TOC 侧栏导航 -- 现状分析

## 1. 文档阅读器布局

### 1.1 全局三栏布局

应用采用 `react-resizable-panels` 实现三栏可调整布局 (`app-shell.tsx`):

```
page-shell
├── page-header (全局导航栏)
└── main (flex: 1, overflow: hidden)
    └── Group (horizontal, height: 100%)
        ├── Panel#sources (defaultSize: 25%, min: 200px, max: 40%)
        │   └── section.panel → panel-head + panel-body(overflow: auto)
        ├── Separator
        ├── Panel#main (defaultSize: 50%, min: 320px, overflow: visible)
        │   └── section.panel → panel-head + panel-body(overflow: hidden, padding: 0) + mainOverlay
        ├── Separator
        └── Panel#studio (defaultSize: 25%, min: 160px, max: 40%)
            └── section.panel → panel-head + panel-body(overflow: auto)
```

关键约束:
- Main 面板的 `panel-body` 设置 `overflow: hidden, padding: 0`，内容区的滚动由子组件自行管理
- Main 面板 `overflow: visible` 是为了 `mainOverlay` (ExplainCard 浮层) 可以溢出面板边界显示

### 1.2 阅读器内部结构

`DocumentReader` 作为 `main` prop 传入 `AppShell`，在 Main 面板的 `panel-body` 内渲染:

```
DocumentReader (height: 100%, flex column)
├── Header (row-between, flexShrink: 0)
│   ├── 左侧: [返回聊天] 按钮 + 文档标题
│   └── 右侧: status badge (completed / processing 等)
├── Content (flex: 1, overflow: auto, ref=scrollContainerRef)
│   └── div (padding: 8px 24px 24px)
│       └── MarkdownViewer
└── SelectionMenu (绝对定位浮层)
```

关键约束:
- `scrollContainerRef` 是整个内容区的滚动容器，`MarkdownViewer` 和未来的 TOC 滚动监听都依赖此 ref
- Header 高度固定 (`flexShrink: 0`)，Content 区域占据剩余空间
注意: Header 右侧的 status badge 与 Sources 面板 `SourceCard` 中的状态徽章完全重复。文档进入阅读器时必定已处于可阅读状态 (`completed` 或 `converted`)，该 badge 实际价值很低，将在 TOC 侧栏方案中移除。
### 1.3 主视图切换

`NotebookWorkspace` 通过 `uiStore.mainView` 控制 Main 面板内呈现 `ChatPanel` 还是 `DocumentReader`:

- 点击文档列表的 "View" 按钮 → `readerStore.openDocument(id)` + `uiStore.setMainView("reader")`
- 点击 "返回聊天" → `uiStore.setMainView("chat")`

TOC 侧栏仅在 `DocumentReader` 中出现，对 `ChatPanel` 无影响。

## 2. Markdown 渲染管线

### 2.1 处理流程

`markdown-pipeline.ts` 定义的转换链:

```
remarkParse          -- Markdown 解析为 mdast
  → remarkGfm       -- GFM 扩展 (表格、删除线等)
  → remarkCjkFriendly -- CJK 字符优化
  → remarkMath*      -- 数学公式 (按需启用)
  → remarkRehype    -- mdast → hast
  → rehypeSlug      -- [关键] 为所有标题生成 id 属性
  → rehypeHighlight* -- 代码高亮 (按需启用)
  → rehypeKatex*     -- KaTeX 渲染 (按需启用)
  → rehypeImgEnhance -- 图片路径规范化 + 懒加载属性
  → rehypeStringify  -- hast → HTML 字符串
```

### 2.2 rehype-slug 的作用

`rehype-slug` 根据标题文本内容生成 URL 友好的 `id` 属性:

- 输入: `<h2>第三章 组合逻辑电路</h2>`
- 输出: `<h2 id="第三章-组合逻辑电路">第三章 组合逻辑电路</h2>`

生成规则 (github-slugger 算法):
1. 转为小写
2. 移除非字母数字字符 (保留中文字符、连字符、空格)
3. 空格替换为连字符 `-`
4. 重复标题追加序号: `id`, `id-1`, `id-2`

这意味着 TOC 的锚点跳转目标已经存在于渲染输出中，无需额外处理。

### 2.3 同步渲染

`renderMarkdownToHtml()` 使用 `processSync()` 同步执行，返回 HTML 字符串。每个 chunk 独立调用此函数，HTML 结果缓存在 `htmlCacheRef` 中。

## 3. Chunk 懒加载机制

### 3.1 分块策略

`MarkdownViewer` 的 `splitMarkdownIntoChunks()` 将长文档按约 24K 字符分块:

| 参数 | 值 | 说明 |
|------|-----|------|
| LARGE_DOC_THRESHOLD_CHARS | 120,000 | 超过此长度才分块 |
| TARGET_CHUNK_CHARS | 24,000 | 目标 chunk 大小 |
| CHUNK_LOAD_STEP | 2 | 每次加载 2 个新 chunk |

分割边界: 在达到 `TARGET_CHUNK_CHARS` 后，遇到标题行 (`/^#{1,6}\s/`) 或空行时切分。若连续 1.6 倍目标大小仍无边界，则强制切分。

### 3.2 加载流程

1. 初始渲染: 根据总 chunk 数显示前 1-3 个 chunk
2. `IntersectionObserver` 监听尾部哨兵元素 (`sentinelRef`)，进入视口时加载下 2 个 chunk
3. `freezeLazyLoad` 标志: 用户正在选择文本 (`isSelecting`) 时冻结加载，防止 DOM 变动干扰选区

### 3.3 TOC 与懒加载的交互

TOC 需要解决的核心问题: **标题列表必须完整，但 DOM 中的标题元素可能尚未加载**。

- TOC 数据源: 从 Markdown 源码 (`content` prop) 提取，而非从 DOM 查询，因此可一次性获取全部标题
- 点击跳转: 若目标标题所在 chunk 尚未加载，需先扩展 `visibleChunkCount` 到包含目标 chunk 的位置，等待渲染后再执行 `scrollIntoView`
- 滚动高亮: 仅对已加载到 DOM 中的标题元素设置 `IntersectionObserver`，随着新 chunk 加载动态更新观察列表

## 4. 文档内容数据

### 4.1 内容获取

- API: `GET /api/v1/documents/{id}/content?format=markdown`
- 返回: `{ document_id, title, format, content, page_count, content_size }`
- `content` 字段为完整的 `content.md` 文本，一次性返回
- 前端通过 TanStack Query 缓存，`DocumentReader` → `contentQuery.data?.content`

### 4.2 现有文档的标题结构

4 份测试文档的标题分布:

| 文档 | 格式 | 处理器 | 内容大小 | 标题层级 |
|------|------|--------|----------|----------|
| 数字电子技术基础简明教程 | PDF | MinerU | ~879K chars | h1-h3，丰富的章节/节结构 |
| 大模型基础_完整版 | PDF | MinerU | ~573K chars | h1-h3，丰富的章节结构 |
| NIST_AI_600-1 | PDF | MinerU | ~408K chars | h1-h4，详细的章节层级 |
| 副本_test_upload | XLSX | MarkItDown | ~2K chars | h2 (sheet名称) |

所有文档都有标题结构，TOC 导航对全部格式有效。

## 5. Reader 状态管理

### 5.1 现有 Store

`reader-store.ts` (zustand) 管理阅读器状态:

```typescript
type ReaderState = {
  currentDocumentId: string | null;
  selection: SelectionState | null;   // 文本选中内容
  isSelecting: boolean;               // 是否正在选择
  isMenuVisible: boolean;             // 右键菜单可见性
  menuPosition: MenuPosition | null;  // 菜单位置
  // ... actions
};
```

TOC 相关状态 (折叠/展开) 可选择:
- **方案 A**: 加入 `reader-store`，跨文档切换时保持 TOC 展开状态
- **方案 B**: 使用 `DocumentReader` 内部的 `useState`，切换文档时重置

推荐方案 A，因为用户打开 TOC 后通常期望它在切换文档时保持打开。

## 6. 存在的技术约束

| 约束 | 影响 | 应对方式 |
|------|------|----------|
| chunk 独立调用 `renderMarkdownToHtml` | 同一标题文本在不同 chunk 中可能生成相同 slug | rehype-slug 的去重仅在单次调用内有效，跨 chunk 需要前端 slug 生成时统一计数 |
| `content-visibility: auto` 导致未可见 chunk 高度不准确 | `scrollIntoView` 可能因高度估算偏差定位不精准 | 跳转后可二次校准，或对小文档 (单 chunk) 无此问题 |
| Main 面板最小宽度 320px | TOC 侧栏 220px + 内容区最小宽度需合理设定 | 内容区最小约 100px 时可触发自动折叠 TOC (响应式) |
| `dangerouslySetInnerHTML` 渲染 | 无法通过 React 组件树直接访问标题元素 | 使用 DOM API (`querySelectorAll`) 查询已渲染的标题 |

## 7. 总结

TOC 侧栏导航具备良好的实施基础:

1. **锚点已就绪**: `rehype-slug` 已为所有标题生成 `id`，跳转零成本
2. **数据可用**: Markdown 源码 (`content` prop) 一次性可用，标题提取无需异步操作
3. **布局可控**: `DocumentReader` 内部为 flexbox 布局，插入侧栏仅需调整为 `flex-direction: row`
4. **状态可扩展**: `reader-store` 可扩展 TOC 折叠状态
5. **主要挑战**: chunk 懒加载场景下的跳转定位和跨 chunk slug 去重
