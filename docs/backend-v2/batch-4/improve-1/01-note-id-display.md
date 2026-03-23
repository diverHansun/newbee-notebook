# improve-1: 笔记卡片 ID 显示与复制

## 背景

当前 diagram 模块在 Studio 面板中，每个图表卡片的右上角显示可点击复制的 `diagram_id` chip。
笔记模块缺少相同的功能，用户无法直观获取 `note_id`，导致在使用 `/note` 触发 Agent 时，
无法方便地通过 ID 引用特定笔记进行查询或操作。

## 目标

在 Studio 面板中为笔记卡片添加 ID 显示与一键复制功能，与 diagram 模块体验对齐。

## 现有实现参考

### diagram 模块的 ID 显示实现

位于 `frontend/src/components/studio/studio-panel.tsx`：

**状态与回调（第 322-354 行）：**

```tsx
const copyDiagramId = useCallback(async (diagramId: string) => {
  await navigator.clipboard.writeText(diagramId);
  setCopiedDiagramId(diagramId);
}, []);

const renderDiagramIdControls = useCallback(
  (diagramId: string, options?: { stopPropagation?: boolean }) => {
    const isCopied = copiedDiagramId === diagramId;
    return (
      <code className="chip" onClick={() => void copyDiagramId(diagramId)}
            title={isCopied ? t(uiStrings.studio.diagramIdCopied) : t(uiStrings.studio.diagramId)}>
        {isCopied ? t(uiStrings.studio.diagramIdCopied) : diagramId}
      </code>
    );
  },
  [copiedDiagramId, copyDiagramId, t]
);
```

**列表视图中的使用（第 601-603 行）：**

```tsx
<div className="row-between" style={{ gap: 8, alignItems: "flex-start" }}>
  <strong>{diagram.title}</strong>
  {renderDiagramIdControls(diagram.diagram_id, { stopPropagation: true })}
</div>
```

**i18n 键（`frontend/src/lib/i18n/strings.ts` 第 290-293 行）：**

```ts
diagramId: { zh: "图表 ID", en: "Diagram ID" },
copyDiagramIdShort: { zh: "复制 ID", en: "Copy ID" },
copyDiagramId: { zh: "复制图表 ID {id}", en: "Copy diagram ID {id}" },
diagramIdCopied: { zh: "图表 ID 已复制", en: "Diagram ID copied" },
```

### 笔记卡片当前结构

位于 `studio-panel.tsx` 第 426-449 行：

```tsx
<button key={note.note_id} className="list-item" onClick={() => openNoteEditor(note.note_id)}>
  <div className="stack-sm">
    <strong>{note.title || t(uiStrings.notes.untitled)}</strong>
    <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
      {note.document_ids.map((documentId) => (
        <span key={documentId} className="chip">{documentMap.get(documentId)?.title ?? documentId}</span>
      ))}
    </div>
    <span className="muted" style={{ fontSize: 11 }}>
      {ti(uiStrings.notes.updatedAt, { date: formatTimestamp(note.updated_at, locale) })}
    </span>
  </div>
</button>
```

当前笔记卡片没有显示 `note_id`，标题行无右侧控件。

## 修改方案

### 1. 重构：抽取通用 ID 复制组件

将 diagram 专用的 `copyDiagramId` / `renderDiagramIdControls` 重构为通用的 `copyItemId` / `renderItemIdControls`，
供笔记和图表共用，避免重复代码。

**状态变更：**

```
- copiedDiagramId / setCopiedDiagramId
+ copiedItemId / setCopiedItemId
```

**通用渲染函数签名：**

```tsx
const renderItemIdControls = useCallback(
  (itemId: string, label: { default: string; copied: string }, options?: { stopPropagation?: boolean }) => {
    const isCopied = copiedItemId === itemId;
    return (
      <code className="chip" ...>
        {isCopied ? label.copied : itemId}
      </code>
    );
  },
  [copiedItemId, ...]
);
```

diagram 和 note 分别传入各自的 i18n label 调用即可。

### 2. 笔记卡片标题行改造

将笔记卡片的标题行从单一 `<strong>` 改为 `row-between` 布局，右侧放置 ID chip：

```tsx
<div className="row-between" style={{ gap: 8, alignItems: "flex-start" }}>
  <strong>{note.title || t(uiStrings.notes.untitled)}</strong>
  {renderItemIdControls(note.note_id, noteIdLabels, { stopPropagation: true })}
</div>
```

### 3. 笔记详情视图添加 ID 显示

在笔记编辑器顶部（标题输入框附近）显示 `note_id` chip，与 diagram 详情视图对齐。

### 4. 新增 i18n 键

在 `frontend/src/lib/i18n/strings.ts` 的 `notes` 区块中新增：

```ts
noteId: { zh: "笔记 ID", en: "Note ID" },
noteIdCopied: { zh: "笔记 ID 已复制", en: "Note ID copied" },
```

## 涉及文件

| 文件 | 改动类型 |
| --- | --- |
| `frontend/src/components/studio/studio-panel.tsx` | 重构 ID 复制逻辑为通用函数；笔记卡片添加 ID chip；笔记详情添加 ID chip |
| `frontend/src/lib/i18n/strings.ts` | 新增 `noteId`、`noteIdCopied` 键 |

## 不涉及的改动

- 后端无需修改：`note_id` 已在所有 API 响应中返回（`NoteResponse`、`NoteListItemResponse`）
- Skill tools 无需修改：`_format_notes()` 已在工具输出中包含 `note ID: {note_id}`
