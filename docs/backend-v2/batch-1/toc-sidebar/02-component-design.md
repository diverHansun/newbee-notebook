# TOC 侧栏导航 -- 组件设计

## 1. 布局方案

### 1.1 整体结构

在 `DocumentReader` 内部将 Content 区域从单列改为横向 flexbox，左侧为 TOC 侧栏，右侧为原有内容滚动区:

```
DocumentReader (height: 100%, flex column)
├── Header (row-between, flexShrink: 0, borderBottom)
│   ├── 左侧: [返回聊天] + 文档标题
│   └── 右侧: [目录 toggle] + status badge
└── Body (flex: 1, display: flex, flex-direction: row, overflow: hidden)
    ├── TocSidebar (width: 220px, 可折叠, borderRight)
    │   ├── 侧栏标题 "目录"
    │   └── 标题列表 (overflow-y: auto)
    └── Content (flex: 1, overflow-y: auto, ref=scrollContainerRef)
        └── div (padding: 8px 24px 24px)
            └── MarkdownViewer
```

### 1.2 折叠行为

TOC 侧栏通过 CSS `width` + `overflow: hidden` 控制折叠:

| 状态 | 侧栏宽度 | 过渡动画 |
|------|----------|----------|
| 展开 | 220px | width 200ms ease-out |
| 折叠 | 0px | width 200ms ease-in |

折叠时侧栏完全消失，内容区自动扩展占满整个 Body。不使用 `display: none`，以保留 DOM 状态并支持动画。

### 1.3 响应式处理

当 Main 面板宽度被用户拖拽缩小时:
- 面板宽度 < 480px: 自动折叠 TOC 侧栏，释放空间给内容区
- 面板宽度恢复 >= 480px: 不自动展开 (避免反复跳动)，由用户手动控制

## 2. Header 改动

### 2.1 移除 Status Badge

当前 Header 右侧显示文档状态徽章 (`completed` / `processing` 等)。此信息与 Sources 面板 `SourceCard` 中的状态徽章完全重复，且文档进入阅读器时必定已处于可阅读状态 (`completed` 或 `converted`)，状态提示的实际价值很低。

**变更**: 移除 Header 中的 `{status && <span className={...}>}` 渲染块，同时清理 `DocumentReader` 内部的 `statusBadgeClass()` 辅助函数 (该函数仅被 Header badge 使用，`SourceCard` 有自己独立的同名函数)。

移除后 Header 右侧空间释放给 TOC toggle 按钮。

### 2.2 Toggle 按钮位置

在 `DocumentReader` 的 Header 右侧区域 (原 status badge 位置)，新增 TOC toggle 按钮:

```
┌──────────────────────────────────────────────────────┐
│ [<- 返回聊天]  数字电子技术基础简明教程_116...pdf      [目录] │
│                                                      ↑     │
│                                                toggle 按钮  │
└──────────────────────────────────────────────────────┘
```

### 2.3 按钮样式

- 使用现有 `btn btn-ghost btn-sm` 样式类
- 文本标签: "目录" (与 i18n 键对应)
- 无标题结构的文档: 按钮不渲染 (而非 disabled)
- 激活状态: 展开时加 `btn-active` 或 `aria-pressed="true"` 以示区分

### 2.4 i18n 键

在 `uiStrings.reader` 下新增:

| 键 | 中文 | 英文 |
|----|------|------|
| `tocToggle` | 目录 | TOC |
| `tocTitle` | 目录 | Table of Contents |

## 3. TOC 侧栏组件

### 3.1 组件文件

新增 `components/reader/toc-sidebar.tsx`:

```typescript
type TocItem = {
  id: string;       // 锚点 ID (与 rehype-slug 生成的一致)
  text: string;     // 标题文本
  level: number;    // 标题层级 1-6
};

type TocSidebarProps = {
  items: TocItem[];           // TOC 数据列表
  activeId: string | null;    // 当前高亮的标题 ID
  isOpen: boolean;            // 展开/折叠状态
  onItemClick: (id: string) => void;  // 点击条目回调
};
```

### 3.2 渲染结构

```html
<aside class="toc-sidebar" aria-label="目录" data-open="{isOpen}">
  <div class="toc-sidebar-header">
    <span>目录</span>
  </div>
  <nav class="toc-sidebar-nav">
    <ul>
      <li class="toc-item toc-level-{level} {active}" data-id="{id}">
        <button onClick={onItemClick(id)}>{text}</button>
      </li>
      ...
    </ul>
  </nav>
</aside>
```

### 3.3 层级缩进

通过 `padding-left` 体现层级关系:

| 标题层级 | CSS 类 | padding-left |
|----------|--------|--------------|
| h1 | `.toc-level-1` | 0px |
| h2 | `.toc-level-2` | 16px |
| h3 | `.toc-level-3` | 32px |
| h4 | `.toc-level-4` | 48px |
| h5, h6 | `.toc-level-5`, `.toc-level-6` | 64px |

### 3.4 激活态样式

当前可见标题对应的 TOC 条目:
- 左侧添加 2px 实色竖线 (`border-left`)
- 文字颜色加深 (使用 CSS 变量 `--foreground`)
- 背景微调 (使用 CSS 变量 `--accent` 的低透明度版本)

未激活条目:
- 文字颜色使用 `--muted-foreground`
- 无左侧竖线

### 3.5 侧栏自身滚动跟随

当内容滚动导致激活项变化时，若新激活项不在 TOC 侧栏可见区域内，对该条目执行 `scrollIntoView({ block: "nearest" })`，使其滚入视口。

## 4. 标题提取 Hook

### 4.1 Hook 文件

新增 `lib/hooks/use-toc.ts`，负责:
1. 从 Markdown 源码提取标题列表
2. 监听内容滚动，维护当前激活标题 ID

### 4.2 标题提取

从 Markdown 源码用正则提取:

```typescript
function extractTocItems(markdown: string): TocItem[] {
  const items: TocItem[] = [];
  const slugCounts = new Map<string, number>();
  const headingRegex = /^(#{1,6})\s+(.+)$/gm;

  let match;
  while ((match = headingRegex.exec(markdown)) !== null) {
    const level = match[1].length;
    const text = match[2].trim();
    const baseSlug = githubSlugify(text);
    const count = slugCounts.get(baseSlug) || 0;
    const id = count === 0 ? baseSlug : `${baseSlug}-${count}`;
    slugCounts.set(baseSlug, count + 1);
    items.push({ id, text, level });
  }

  return items;
}
```

**为什么从源码而非 DOM 提取**:
- 源码一次性可用 (`content` prop)，不受 chunk 懒加载限制
- 可在首次渲染前生成完整 TOC

**slug 算法一致性**:
- 必须与 `rehype-slug` 使用的 `github-slugger` 算法保持一致
- 前端直接引用 `github-slugger` 包 (已作为 `rehype-slug` 的依赖存在)

### 4.3 滚动高亮

```typescript
function useActiveHeading(
  scrollContainerRef: RefObject<HTMLElement | null>,
  tocItems: TocItem[]
): string | null {
  // 返回当前视口中最靠近顶部的标题 ID
}
```

实现要点:
- 使用 `IntersectionObserver` 监听所有已加载到 DOM 中的标题元素
- `rootMargin: "-10% 0px -80% 0px"` -- 仅将视口上方 10%-20% 区域作为激活判定区
- 当多个标题同时可见时，取最上方的一个
- 观察目标为 `scrollContainerRef.current.querySelectorAll("h1[id], h2[id], h3[id], h4[id], h5[id], h6[id]")`

### 4.4 观察列表动态更新

由于 chunk 懒加载，新标题元素会动态出现在 DOM 中。需要在 `visibleChunkCount` 变化时重建 Observer:

```typescript
useEffect(() => {
  // visibleChunkCount 变化 → 重新查询标题元素 → 重建 IntersectionObserver
}, [visibleChunkCount, tocItems]);
```

为检测 `visibleChunkCount` 变化，可选方案:
- 方案 A: `MarkdownViewer` 暴露一个 `onChunkRender` 回调
- 方案 B: 使用 `MutationObserver` 监听容器子节点变化
- 推荐方案 B，无需修改 `MarkdownViewer` 接口

## 5. 点击跳转逻辑

### 5.1 基本流程

```
用户点击 TOC 项 (id)
  → 查找 DOM: document.getElementById(id)
  → 如果找到: scrollIntoView({ behavior: "smooth", block: "start" })
  → 如果未找到: 目标在未加载的 chunk 中，触发展开后跳转
```

### 5.2 跳转到未加载 chunk

当目标标题所在 chunk 尚未加载时:

1. 根据 TOC 项在源码中的位置，计算其属于第几个 chunk
2. 将 `visibleChunkCount` 扩展到包含目标 chunk
3. 等待渲染完成 (使用 `requestAnimationFrame` 或 `MutationObserver`)
4. 执行 `scrollIntoView`

具体实现: `MarkdownViewer` 需要暴露一个命令式接口:

```typescript
// 通过 useImperativeHandle 暴露
type MarkdownViewerHandle = {
  expandToChunk: (chunkIndex: number) => void;
};
```

或者更简单的方案: 将 `setVisibleChunkCount` 提升到 `DocumentReader` 层管理，TOC 跳转时直接调用。推荐此方案，因为状态提升比命令式接口更符合 React 数据流。

### 5.3 chunk 索引计算

在标题提取阶段，同步计算每个标题属于哪个 chunk:

```typescript
type TocItem = {
  id: string;
  text: string;
  level: number;
  chunkIndex: number;  // 所属 chunk 的索引
};
```

复用 `splitMarkdownIntoChunks` 的分割逻辑，在提取标题时记录每个标题的字符偏移量，映射到 chunk 索引。

## 6. 状态管理

### 6.1 TOC 展开状态

在 `reader-store.ts` 中扩展:

```typescript
type ReaderState = {
  // 现有字段...
  isTocOpen: boolean;
  setTocOpen: (open: boolean) => void;
  toggleToc: () => void;
};
```

初始值 `isTocOpen: true`。切换文档时不重置此值 (在 `openDocument` action 中保留)。

### 6.2 数据流

```
content (Markdown 源码)
  → extractTocItems() → TocItem[]         -- 静态提取，useMemo 缓存
  → useActiveHeading(scrollRef, items)     -- 滚动监听，返回 activeId
  → TocSidebar(items, activeId, isOpen)    -- 渲染
  → onItemClick → scrollToHeading(id)      -- 跳转
```

## 7. 样式规范

### 7.1 新增样式文件

`styles/toc-sidebar.css`，独立于 `markdown-content.css`:

```css
/* 侧栏容器 */
.toc-sidebar {
  width: 220px;
  flex-shrink: 0;
  border-right: 1px solid hsl(var(--border));
  overflow: hidden;
  transition: width 200ms ease;
}
.toc-sidebar[data-open="false"] {
  width: 0;
  border-right: none;
}

/* 标题区 */
.toc-sidebar-header {
  padding: 12px 16px 8px;
  font-size: 12px;
  font-weight: 600;
  color: hsl(var(--muted-foreground));
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* 导航列表 */
.toc-sidebar-nav {
  overflow-y: auto;
  flex: 1;
  padding: 0 8px 16px;
}
.toc-sidebar-nav ul {
  list-style: none;
  margin: 0;
  padding: 0;
}

/* 条目 */
.toc-item button {
  display: block;
  width: 100%;
  text-align: left;
  background: none;
  border: none;
  border-left: 2px solid transparent;
  padding: 4px 8px;
  font-size: 13px;
  line-height: 1.4;
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  border-radius: 0 4px 4px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.toc-item button:hover {
  background: hsl(var(--accent));
  color: hsl(var(--foreground));
}

/* 激活态 */
.toc-item.active button {
  border-left-color: hsl(var(--bee-yellow));
  color: hsl(var(--foreground));
  font-weight: 500;
}

/* 层级缩进 */
.toc-level-1 button { padding-left: 8px; }
.toc-level-2 button { padding-left: 24px; }
.toc-level-3 button { padding-left: 40px; }
.toc-level-4 button { padding-left: 56px; }
.toc-level-5 button,
.toc-level-6 button { padding-left: 72px; }
```

### 7.2 设计语言

- 配色跟随现有 CSS 变量体系 (`--border`, `--accent`, `--muted-foreground`, `--bee-yellow`)
- 激活态左侧竖线使用项目主题色 `--bee-yellow`，与 Header 中的品牌下划线一致
- 字体大小 13px，与 Sources 面板的文档列表项保持一致
- 文字溢出截断 (`text-overflow: ellipsis`)，避免长标题撑破布局

## 8. 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `components/reader/toc-sidebar.tsx` | 新增 | TOC 侧栏组件 |
| `lib/hooks/use-toc.ts` | 新增 | 标题提取 + 滚动高亮 hook |
| `styles/toc-sidebar.css` | 新增 | 侧栏样式 |
| `components/reader/document-reader.tsx` | 修改 | 移除 status badge + 集成 TOC 侧栏 + toggle 按钮，清理 `statusBadgeClass` 函数 |
| `stores/reader-store.ts` | 修改 | 新增 `isTocOpen` 状态 |
| `lib/i18n/strings.ts` | 修改 | 新增 TOC 相关 i18n 键 |
| `components/reader/markdown-viewer.tsx` | 不改动 | -- |
| `components/reader/markdown-pipeline.ts` | 不改动 | -- |
| `components/layout/app-shell.tsx` | 不改动 | -- |
