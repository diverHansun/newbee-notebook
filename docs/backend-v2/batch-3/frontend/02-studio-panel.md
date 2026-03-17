# Studio Panel 设计

## 1. 设计目标

将 Studio Panel 从 "Coming Soon" 占位状态升级为功能面板，采用卡片网格首屏 + 功能详情视图的分层导航模式。Batch-3 实现 Notes & Marks 功能卡片，为 batch-4 的 Mind Map 等功能预留扩展位。

## 2. 整体结构

### 2.1 分层导航

Studio Panel 内部有三级视图，通过 Zustand store 中的 `studioView` 状态控制切换：

```
Studio Home (卡片网格)
  -> Notes & Marks 视图 (列表)
    -> Note Editor 视图 (编辑)
```

每级视图占据 Studio Panel 全部空间，通过返回按钮回到上一级。

### 2.2 Studio Home：卡片网格

首屏为 2 列卡片网格，每张卡片代表一个功能入口：

```
+----------------+  +----------------+
|  Notes &       |  |  Mind Map      |
|  Marks         |  |  (Coming Soon) |
+----------------+  +----------------+
+----------------+  +----------------+
|  (Future)      |  |  (Future)      |
|                |  |                |
+----------------+  +----------------+
```

- Batch-3 可用：Notes & Marks
- Batch-4 预留：Mind Map（灰显，不可点击）
- 未来扩展位：灰显占位

卡片样式复用 `.card` + `.card-interactive` 类。不可用卡片增加 `opacity: 0.5` 和 `pointer-events: none`。

每张卡片包含：图标区域、功能名称、简短描述。

### 2.3 Props 传递

`NotebookWorkspace` 将 `notebookId` 传给 `StudioPanel`：

```typescript
type StudioPanelProps = {
  notebookId: string;
};
```

AppShell 的 `rightPanel` slot 需要支持传递 props。

## 3. Notes & Marks 视图

点击 "Notes & Marks" 卡片后进入此视图。内部分为 Notes 区（主）和 Marks 区（辅，可折叠）。

### 3.1 布局

```
+---------------------------------+
| [<- Studio]  [Filter: doc]      |
+---------------------------------+
| Notes                     [+]   |
| +-----------------------------+ |
| | Note Title A                | |
| | docs: doc1.pdf, doc2.pdf    | |
| | Updated: 2026-03-17         | |
| +-----------------------------+ |
| +-----------------------------+ |
| | Note Title B                | |
| | docs: doc3.pdf              | |
| +-----------------------------+ |
+---------------------------------+
| > Marks (3)          [Collapse] |
| +-----------------------------+ |
| | "anchor text preview..."    | |
| |  -- doc1.pdf                | |
| +-----------------------------+ |
| | "anchor text preview..."    | |
| |  -- doc1.pdf                | |
| +-----------------------------+ |
+---------------------------------+
```

### 3.2 Notes 区

数据来源（resource-nested URL，与后端 API 层对齐）：

```
GET /api/v1/notebooks/{notebookId}/notes
GET /api/v1/notebooks/{notebookId}/notes?document_id={docId}  (筛选)
```

展示当前 notebook 中所有 documents 关联的 notes。文档筛选下拉列出当前 notebook 的 documents，选择后按 `document_id` 过滤。

Note 卡片信息：
- 标题
- 关联文档列表（pill 标签）
- 更新时间

点击 note 卡片进入 Note Editor 视图。

"+" 按钮调用 `POST /api/v1/notes` 创建空 note。如果当前有文档筛选（docFilter 非空），创建时自动传入 `document_ids: [docFilter]` 将新 note 与该文档关联。创建成功后直接进入编辑视图。

### 3.3 Marks 区

Marks 区默认折叠，点击标题栏展开。

数据来源（resource-nested URL，与后端 API 层对齐）：

```
GET /api/v1/notebooks/{notebookId}/marks
GET /api/v1/notebooks/{notebookId}/marks?document_id={docId}  (筛选，后续扩展)
```

展示当前 notebook 内 documents 中的 marks，**按 document 分组**展示。每个分组标题为文档名称，下方列出该文档的 marks。

筛选逻辑与 Notes 区共享同一个文档筛选下拉。选择文档后，Notes 和 Marks 同时按该文档过滤。

Mark 项展示：
- `anchor_text` 截断显示（前 60 字符）
- 所属文档名称

Mark 项交互：
- 点击：联动 Reader，打开对应文档并滚动到 mark 位置
- 右键菜单或长按："复制引用" 复制 `[[mark:{mark_id}]]` 到剪贴板

### 3.4 activeMarkId 联动

当 Reader 中点击书签边距图标时，`studioStore.activeMarkId` 更新。Notes & Marks 视图响应：
- 如果当前不在 Notes & Marks 视图，自动切换过来
- Marks 区自动展开
- 匹配的 mark 项高亮显示（短暂的背景色闪烁动画）

## 4. Note Editor 视图

### 4.1 布局

```
+---------------------------------+
| [<- Back]              [Delete] |
+---------------------------------+
| Title: [________________]       |
+---------------------------------+
| Docs:                           |
| [doc1.pdf x] [doc2.pdf x] [+]  |
+---------------------------------+
| +-----------------------------+ |
| | Markdown editor (textarea)  | |
| |                             | |
| | Note content here...        | |
| | Reference: [[mark:abc123]]  | |
| |                             | |
| +-----------------------------+ |
| [Insert Mark]     Saved         |
+---------------------------------+
| > Available Marks (5)           |
| [Filter: doc1.pdf]              |
| "anchor text..."       [Insert] |
| "anchor text..."       [Insert] |
+---------------------------------+
```

### 4.2 标题编辑

`<input>` 元素，`onBlur` 或 Enter 时触发保存。

### 4.3 文档关联标签

以 pill/chip 样式展示关联文档，每个 pill 带 "x" 按钮用于解除关联。"+" 按钮弹出当前 notebook 的 documents 选择器，选择后调用关联 API。

- 添加关联：`POST /api/v1/notes/{noteId}/documents`（请求体 `{ "document_id": "uuid" }`）
- 解除关联：`DELETE /api/v1/notes/{noteId}/documents/{documentId}`（需确认，弹出 ConfirmDialog）

### 4.4 Markdown 编辑区

v1 使用 `<textarea>` 实现纯文本 Markdown 编辑。

编辑区特性：
- 占据 Editor 视图的主要空间
- 等宽字体
- 行号（可选，v1 不做）

### 4.5 Mark 引用插入：双通道

**通道 A：`[[` 行内触发器（主要方式）**

用户在 textarea 中输入 `[[` 时，在光标位置弹出浮动选择器：

1. 监听 textarea 的 `onChange` 事件，检测光标前两个字符是否为 `[[`
2. 计算光标在 textarea 中的像素位置（通过 mirror div 或 `getCaretCoordinates` 工具函数）
3. 弹出浮动 popover，列出当前 note 关联文档的 marks
4. popover 内支持搜索（模糊匹配 `anchor_text`）
5. 键盘导航：上下键选择，Enter 确认，Escape 取消
6. 选中后在 textarea 光标位置插入 `[[mark:{mark_id}]]`，关闭 popover

数据来源：优先使用 note 关联文档的 marks，若无关联文档则使用 notebook 全部 marks。

**通道 B：底部 Marks 面板点击插入（辅助方式）**

Note Editor 底部有可折叠的 "Available Marks" 面板：

- 列出当前 note 关联文档的 marks
- 可按文档筛选
- 每个 mark 项右侧有 "Insert" 按钮
- 点击 Insert，在 textarea 当前光标位置插入 `[[mark:{mark_id}]]`

### 4.6 `[[mark:id]]` 渲染

在 textarea 编辑模式下，`[[mark:id]]` 保持原始文本。

后续批次可增加 preview 模式，将 `[[mark:id]]` 渲染为可点击的 pill，显示对应的 `anchor_text`，点击后联动 Reader 跳转。v1 中 preview 模式为可选。

### 4.7 自动保存

保存策略：
- 内容变更后启动 5 秒 debounce 计时器
- Ctrl+S / Cmd+S 立即保存
- 切换视图（返回列表）时如有未保存变更立即保存

保存 API：

```
PATCH /api/v1/notes/{noteId}
{
  "title": "...",    // 可选
  "content": "..."   // 可选
}
```

`note_mark_refs` 同步：后端在处理 `updateNote` 时，解析 content 中的 `[[mark:xxx]]` 引用，自动同步 `note_mark_refs` 关联表。前端无需单独调用 Mark 引用的增删 API，只需保存 content 即可。此职责归后端 NoteService。

保存状态指示器：
- "Unsaved" / 未保存 — 有变更未保存
- "Saving..." / 保存中 — 正在请求
- "Saved" / 已保存 — 保存成功

### 4.8 删除

点击删除按钮弹出 `ConfirmDialog`（复用现有组件，variant="danger"）。确认后调用 `DELETE /api/v1/notes/{noteId}`，成功后返回列表视图。

## 5. 状态管理

### 5.1 studio-store.ts

新建 Zustand store：

```typescript
type StudioView = "home" | "notes-marks" | "note-editor";

type StudioState = {
  studioView: StudioView;
  activeNoteId: string | null;
  activeMarkId: string | null;
  docFilter: string | null;

  navigateTo: (view: StudioView) => void;
  openNoteEditor: (noteId: string) => void;
  backToList: () => void;
  backToHome: () => void;
  setActiveMarkId: (markId: string | null) => void;
  setDocFilter: (documentId: string | null) => void;
};
```

### 5.2 数据请求

使用 TanStack Query，新增 API 模块 `notes.ts` 和 `marks.ts`，遵循现有 `documents.ts` 的模式：

```typescript
// lib/api/notes.ts
export function listNotes(notebookId: string, params?: { document_id?: string }) { ... }
  // GET /api/v1/notebooks/{notebookId}/notes?document_id=xxx
export function getNote(noteId: string) { ... }
  // GET /api/v1/notes/{noteId}
export function createNote(input: { title: string; content?: string; document_ids?: string[] }) { ... }
  // POST /api/v1/notes
export function updateNote(noteId: string, input: { title?: string; content?: string }) { ... }
  // PATCH /api/v1/notes/{noteId}
export function deleteNote(noteId: string) { ... }
  // DELETE /api/v1/notes/{noteId}
export function addNoteDocument(noteId: string, documentId: string) { ... }
  // POST /api/v1/notes/{noteId}/documents  body: { document_id }
export function removeNoteDocument(noteId: string, documentId: string) { ... }
  // DELETE /api/v1/notes/{noteId}/documents/{documentId}

// lib/api/marks.ts
export function listMarksByDocument(documentId: string) { ... }
  // GET /api/v1/documents/{documentId}/marks
export function listMarksByNotebook(notebookId: string) { ... }
  // GET /api/v1/notebooks/{notebookId}/marks
export function createMark(documentId: string, input: { anchor_text: string; char_offset: number }) { ... }
  // POST /api/v1/documents/{documentId}/marks
export function deleteMark(markId: string) { ... }
  // DELETE /api/v1/marks/{markId}
```

Query Key 规划（详见 04-i18n-and-types.md 第 5 节）：

| Query Key | 用途 |
|-----------|------|
| ["notes", notebookId, docFilter] | Notes 列表 |
| ["note", noteId] | 单个 Note 详情 |
| ["note-documents", noteId] | Note 关联的文档列表 |
| ["marks", "document", documentId] | 单文档 marks（Reader 用） |
| ["marks", "notebook", notebookId] | Notebook marks（Studio 用） |

## 6. 组件拆分

```
StudioPanel
  StudioHome           (卡片网格首屏)
    FeatureCard        (单个功能卡片)
  NotesMarksView       (Notes & Marks 列表视图)
    NoteCard           (Note 列表项)
    MarksSection       (Marks 折叠区)
      MarkItem         (Mark 列表项)
  NoteEditor           (Note 编辑视图)
    DocTagList         (文档关联标签)
    MarkInlinePicker   (双括号触发的 mark 选择器)
    AvailableMarks     (底部可折叠 marks 面板)
    SaveIndicator      (保存状态指示器)
```
