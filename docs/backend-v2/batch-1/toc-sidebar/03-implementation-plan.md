# TOC 侧栏导航 -- 实施计划

## 1. 任务概览

共 4 个阶段，按依赖顺序执行:

```
阶段 1: 数据层 (标题提取 + slug 生成)
  ↓
阶段 2: 组件层 (TocSidebar 组件 + 样式)
  ↓
阶段 3: 集成层 (DocumentReader 改造 + 状态管理)
  ↓
阶段 4: 交互优化 (懒加载协同 + 滚动高亮)
```

纯前端实现，无后端改动，无数据库迁移。

## 2. 阶段 1 -- 数据层

### 2.1 标题提取函数

**文件**: `lib/hooks/use-toc.ts`

**任务**:
- 实现 `extractTocItems(markdown: string): TocItem[]`
- 使用正则 `/^(#{1,6})\s+(.+)$/gm` 从 Markdown 源码提取标题
- 使用 `github-slugger` 包生成与 `rehype-slug` 一致的锚点 ID
- 计算每个标题所属的 chunk 索引 (复用 `splitMarkdownIntoChunks` 的分割逻辑)

**类型定义**:
```typescript
type TocItem = {
  id: string;
  text: string;
  level: number;
  chunkIndex: number;
};
```

**验收标准**:
- 对 4 份测试文档的 Markdown 内容调用 `extractTocItems()`，生成的 `id` 与浏览器中对应标题元素的 `id` 属性完全一致
- `chunkIndex` 与 `splitMarkdownIntoChunks()` 的实际分块结果对应正确

### 2.2 依赖确认

**任务**:
- 确认 `github-slugger` 是否已在 `node_modules` 中 (作为 `rehype-slug` 的传递依赖)
- 若未直接可用，在 `package.json` 中显式添加 `github-slugger` 依赖

## 3. 阶段 2 -- 组件层

### 3.1 TocSidebar 组件

**文件**: `components/reader/toc-sidebar.tsx`

**任务**:
- 实现 `TocSidebar` 组件，接收 `items`, `activeId`, `isOpen`, `onItemClick` 四个 props
- 渲染为 `<aside>` + `<nav>` + `<ul>` 语义结构
- 层级缩进通过 CSS 类 `.toc-level-{n}` 控制
- 激活项自动 scrollIntoView (侧栏内部的滚动跟随)
- 无标题时不渲染 (返回 null)

**验收标准**:
- 渲染的标题列表与文档标题结构一致
- 层级缩进视觉正确
- 激活项有明显的视觉区分 (左侧竖线 + 文字加深)

### 3.2 样式文件

**文件**: `styles/toc-sidebar.css`

**任务**:
- 实现侧栏容器、标题区、导航列表、条目、层级缩进、激活态的完整样式
- 折叠/展开过渡动画 (`width` transition 200ms)
- 使用现有 CSS 变量 (`--border`, `--accent`, `--muted-foreground`, `--bee-yellow`)

**验收标准**:
- 折叠/展开动画流畅无闪烁
- 配色与整体主题一致
- 长标题文本截断显示

### 3.3 i18n 键

**文件**: `lib/i18n/strings.ts`

**任务**:
- 在 `uiStrings.reader` 中新增 `tocToggle` 和 `tocTitle` 键
- 中文: "目录" / "目录" ; 英文: "TOC" / "Table of Contents"

## 4. 阶段 3 -- 集成层

### 4.1 Reader Store 扩展

**文件**: `stores/reader-store.ts`

**任务**:
- 新增 `isTocOpen: boolean` 状态，初始值 `true`
- 新增 `setTocOpen(open: boolean)` 和 `toggleToc()` action
- `openDocument` action 中保留 `isTocOpen` 不重置 (用户偏好跨文档保持)

### 4.2 DocumentReader 改造

**文件**: `components/reader/document-reader.tsx`

**任务**:

**Header 改动**:
- 移除右侧 status badge 渲染 (`{status && <span>...}`)，该状态与 Sources 面板 `SourceCard` 重复
- 清理 `DocumentReader` 内部的 `statusBadgeClass()` 辅助函数 (仅被 Header badge 使用)
- 在原 status badge 位置新增 TOC toggle 按钮
- 按钮使用 `btn btn-ghost btn-sm` 样式
- 仅在 `tocItems.length > 0` 时渲染按钮

**Body 改动**:
- 将现有 Content 区域包裹在横向 flex 容器中
- 左侧插入 `<TocSidebar>`
- 右侧保持原有的 `scrollContainerRef` 内容区

**数据流**:
- 调用 `extractTocItems(content)` 获取 TOC 数据 (useMemo)
- 调用 `useActiveHeading(scrollContainerRef, tocItems)` 获取当前激活项
- 将 `isTocOpen` 从 `reader-store` 读取

**验收标准**:
- toggle 按钮正确控制 TOC 展开/折叠
- 无标题文档不显示 toggle 按钮和 TOC
- 折叠时不影响已有的文本选中、解释/总结功能

## 5. 阶段 4 -- 交互优化

### 5.1 滚动高亮

**文件**: `lib/hooks/use-toc.ts` (useActiveHeading 部分)

**任务**:
- 使用 `IntersectionObserver` 监听已加载的标题元素
- `rootMargin: "-10% 0px -80% 0px"` 设定激活判定区域为视口上方 10%-20%
- 使用 `MutationObserver` 监听容器子节点变化，新 chunk 加载后重建观察列表

**验收标准**:
- 滚动内容时 TOC 激活项实时跟随
- 新 chunk 加载后，其中的标题加入观察列表
- 快速滚动时无性能抖动

### 5.2 点击跳转已加载标题

**任务**:
- `onItemClick` 回调: `document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" })`

**验收标准**:
- 点击 TOC 条目平滑滚动到对应标题位置

### 5.3 点击跳转未加载标题

**任务**:
- 若 `document.getElementById(id)` 返回 null，说明目标在未加载 chunk 中
- 利用 `TocItem.chunkIndex`，将 `visibleChunkCount` 扩展到 `chunkIndex + 1`
- 等待渲染完成 (requestAnimationFrame 后重试 getElementById)，再执行 scrollIntoView
- 状态提升方案: 将 `visibleChunkCount` 的管理从 `MarkdownViewer` 内部提升到 `DocumentReader`，或通过 `useImperativeHandle` 暴露 `expandToChunk` 方法

**验收标准**:
- 点击距离当前位置较远的标题 (跨多个未加载 chunk) 能正确跳转
- 跳转后 IntersectionObserver 正确更新激活项

## 6. 依赖关系

```
阶段 1 (数据层)
│  extractTocItems() + TocItem 类型
│  github-slugger 依赖确认
│
├──→ 阶段 2 (组件层)
│      TocSidebar 组件 + CSS 样式 + i18n
│
├──→ 阶段 3 (集成层)    [依赖阶段 1 + 2]
│      reader-store 扩展
│      DocumentReader 布局改造
│
└──→ 阶段 4 (交互优化)  [依赖阶段 3]
       滚动高亮 + 跳转逻辑
```

阶段 1 和阶段 2 的部分工作可并行 (TocSidebar 组件可用 mock 数据开发)。

## 7. 风险评估

| 风险 | 等级 | 说明 | 缓解措施 |
|------|------|------|----------|
| slug 算法不一致 | 中 | 自行生成的 slug 与 rehype-slug 输出不匹配 | 直接引用 `github-slugger` 包，编写单元测试对比 |
| content-visibility 导致跳转偏移 | 低 | 未渲染 chunk 的高度估算不准确 | 跳转后增加二次校准 (延迟 100ms 再 scrollIntoView) |
| 长文档标题过多 | 低 | 数百个标题导致 TOC 列表过长 | 当前文档最大标题数约 200 个，列表渲染压力可控; 后续可考虑折叠子层级 |
| 面板宽度不足 | 低 | 用户将 Main 面板拖得很窄 | 响应式自动折叠 TOC (< 480px 阈值) |

## 8. 范围外 (不在本次实施中)

- TOC 子层级折叠/展开 (如 h2 下折叠所有 h3): 首版呈现完整列表，后续按需添加
- TOC 搜索/过滤功能: 标题数量有限，暂不需要
- TOC 拖拽调整宽度: 保持固定 220px，避免增加交互复杂度
- 后端返回 TOC 数据: 前端即可完成，无需后端参与

## 9. 验收流程

1. 打开大型 PDF 文档 (数字电子技术基础简明教程, ~879K chars)，确认 TOC 完整显示所有章节
2. 点击任意 TOC 条目，确认平滑滚动到对应位置
3. 手动滚动内容，确认 TOC 激活项实时跟随
4. 点击文档末尾章节 (需加载未加载 chunk)，确认能正确展开并跳转
5. 点击 toggle 按钮，确认折叠/展开动画流畅
6. 折叠 TOC 后进行文本选中 + 解释/总结操作，确认功能不受影响- 确认 Header 右侧不再显示 status badge，仅显示 TOC toggle 按钮7. 打开 XLSX 文档 (副本_test_upload)，确认 h2 sheet 标题正确显示在 TOC 中
8. 切换文档后确认 TOC 展开状态保持不变
9. 将 Main 面板拖到极窄宽度，确认 TOC 自动折叠
10. 切换中英文语言，确认 TOC 按钮标签正确显示
