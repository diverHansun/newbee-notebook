# 国际化字符串与 TypeScript 类型定义

## 1. 设计目标

集中规划 batch-3 新增的所有用户可见文本的国际化字符串，以及新增的 TypeScript 类型定义。确保所有文本通过 `uiStrings` 管理，支持中英文。

## 2. 国际化字符串规划

### 2.1 现有模式

项目使用自定义 i18n 方案：
- 字符串定义在 `frontend/src/lib/i18n/strings.ts` 中
- 每个字符串为 `LocalizedString` 类型（`{ zh: string; en: string }`）
- 通过 `useLang()` hook 的 `t()` 和 `ti()` 函数获取翻译文本
- 插值使用 `{variableName}` 语法

### 2.2 新增字符串分组

#### selectionMenu 组（扩展现有）

```typescript
selectionMenu: {
  explain: { zh: "解释", en: "Explain" },     // 已有
  conclude: { zh: "总结", en: "Conclude" },   // 已有
  bookmark: { zh: "书签", en: "Bookmark" },   // 新增
}
```

#### studio 组（扩展现有）

```typescript
studio: {
  comingSoon: { zh: "即将推出", en: "Coming Soon" },              // 已有
  title: { zh: "Studio", en: "Studio" },                         // 新增
  notesAndMarks: { zh: "笔记与书签", en: "Notes & Marks" },       // 新增
  mindMap: { zh: "思维导图", en: "Mind Map" },                    // 新增
  backToStudio: { zh: "返回 Studio", en: "Back to Studio" },     // 新增
  backToList: { zh: "返回列表", en: "Back to list" },             // 新增
}
```

#### notes 组（新增）

```typescript
notes: {
  title: { zh: "笔记", en: "Notes" },
  createNote: { zh: "新建笔记", en: "New Note" },
  editNote: { zh: "编辑笔记", en: "Edit Note" },
  deleteNote: { zh: "删除笔记", en: "Delete Note" },
  deleteNoteConfirm: { zh: "确定要删除这条笔记吗？关联的文档标签会一并移除。", en: "Are you sure you want to delete this note? Associated document tags will be removed." },
  untitled: { zh: "无标题", en: "Untitled" },
  noNotes: { zh: "暂无笔记", en: "No notes yet" },
  notePlaceholder: { zh: "开始写笔记...", en: "Start writing..." },
  titlePlaceholder: { zh: "笔记标题", en: "Note title" },
  associatedDocs: { zh: "关联文档", en: "Associated documents" },
  addDocument: { zh: "添加文档", en: "Add document" },
  removeDocConfirm: { zh: "确定要解除笔记与文档 {title} 的关联吗？", en: "Remove association with document {title}?" },
  insertMark: { zh: "插入书签", en: "Insert bookmark" },
  availableMarks: { zh: "可用书签", en: "Available bookmarks" },
  noAvailableMarks: { zh: "暂无可用书签", en: "No bookmarks available" },
  saveStatus: {
    saved: { zh: "已保存", en: "Saved" },
    saving: { zh: "保存中...", en: "Saving..." },
    unsaved: { zh: "未保存", en: "Unsaved" },
  },
  updatedAt: { zh: "更新于 {date}", en: "Updated {date}" },
  noteCount: { zh: "{n} 条笔记", en: "{n} notes" },
}
```

#### marks 组（新增）

```typescript
marks: {
  title: { zh: "书签", en: "Bookmarks" },
  markCount: { zh: "{n} 个书签", en: "{n} bookmarks" },
  noMarks: { zh: "暂无书签", en: "No bookmarks yet" },
  fromDocument: { zh: "来自《{title}》", en: "From \"{title}\"" },
  copyReference: { zh: "复制引用", en: "Copy reference" },
  referenceCopied: { zh: "引用已复制", en: "Reference copied" },
  filterByDoc: { zh: "按文档筛选", en: "Filter by document" },
  allDocuments: { zh: "全部文档", en: "All documents" },
  bookmarkCreated: { zh: "书签已创建", en: "Bookmark created" },
  bookmarkCreateFailed: { zh: "书签创建失败", en: "Failed to create bookmark" },
}
```

#### slashCommand 组（新增）

```typescript
slashCommand: {
  hint: { zh: "输入 / 查看可用命令", en: "Type / to see available commands" },
  noteDescription: { zh: "笔记和书签管理", en: "Notes & Marks management" },
  mindmapDescription: { zh: "思维导图", en: "Mind Map" },
}
```

#### confirmation 组（新增）

```typescript
confirmation: {
  title: { zh: "确认操作", en: "Confirm action" },
  confirm: { zh: "确认", en: "Confirm" },
  reject: { zh: "拒绝", en: "Reject" },
  confirmed: { zh: "已确认", en: "Confirmed" },
  rejected: { zh: "已拒绝", en: "Rejected" },
  timeout: { zh: "已超时", en: "Timed out" },
  toolAction: {
    update_note: { zh: "更新笔记", en: "Update note" },
    delete_note: { zh: "删除笔记", en: "Delete note" },
    disassociate_note_document: { zh: "解除文档关联", en: "Remove document association" },
  },
}
```

## 3. TypeScript 类型定义

### 3.1 API 响应类型

在 `types.ts` 中新增：

```typescript
// --- Note ---

// Note 详情（GET /api/v1/notes/{noteId} 响应）
export type Note = {
  note_id: string;
  title: string;
  content: string;
  document_ids: string[];
  marks: NoteMark[];
  created_at: string;
  updated_at: string;
};

// Note 列表项（GET /api/v1/notebooks/{notebookId}/notes 响应）
export type NoteListItem = {
  note_id: string;
  title: string;
  document_ids: string[];
  mark_count: number;
  created_at: string;
  updated_at: string;
};

// Note 中引用的 mark 摘要
export type NoteMark = {
  mark_id: string;
  document_id: string;
  anchor_text: string;
  char_offset: number;
};

// Note 关联的文档信息（GET /api/v1/notes/{noteId}/documents 响应）
export type NoteDocumentTag = {
  document_id: string;
  title: string;
};

export type NoteCreateInput = {
  title: string;
  content?: string;
  document_ids?: string[];
};

export type NoteUpdateInput = {
  title?: string;
  content?: string;
};

// --- Mark ---

export type Mark = {
  mark_id: string;
  document_id: string;
  anchor_text: string;
  char_offset: number;
  comment: string | null;
  created_at: string;
  updated_at: string;
};

// createMark 的 document_id 在 URL 路径中，不在 body 中
export type MarkCreateInput = {
  anchor_text: string;
  char_offset: number;
  comment?: string;
};

// --- SSE Event ---

export type SseEventConfirmation = {
  type: "confirmation_request";
  request_id: string;
  tool_name: string;
  tool_args: Record<string, unknown>;
  description: string;
};

// SseEvent 联合类型扩展
export type SseEvent =
  | SseEventStart
  | SseEventContent
  | SseEventThinking
  | SseEventSources
  | SseEventDone
  | SseEventError
  | SseEventHeartbeat
  | SseEventConfirmation;

// --- Chat Message 扩展 ---

export type PendingConfirmation = {
  requestId: string;
  toolName: string;
  toolArgs: Record<string, unknown>;
  description: string;
  status: "pending" | "confirmed" | "rejected" | "timeout";
};
```

### 3.2 Store 类型

studio-store 类型：

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

chat-store ChatMessage 扩展：

```typescript
type ChatMessage = {
  // ... 现有字段
  pendingConfirmation?: PendingConfirmation;
};
```

### 3.3 组件 Props 类型

```typescript
// SlashCommandHint
type SlashCommandHintProps = {
  input: string;
  onSelect: (command: string) => void;
  onDismiss: () => void;
};

// ConfirmationCard
type ConfirmationCardProps = {
  confirmation: PendingConfirmation;
  onConfirm: () => void;
  onReject: () => void;
};

// StudioPanel
type StudioPanelProps = {
  notebookId: string;
};

// NoteEditor
type NoteEditorProps = {
  noteId: string;
  notebookId: string;
  onBack: () => void;
};

// MarkInlinePicker
type MarkInlinePickerProps = {
  marks: Mark[];
  position: { top: number; left: number };
  onSelect: (markId: string) => void;
  onDismiss: () => void;
  filter: string;
};
```

## 4. API 模块规划

### 4.1 notes.ts

```typescript
// GET /api/v1/notebooks/{notebookId}/notes?document_id=xxx
export function listNotes(
  notebookId: string,
  params?: { document_id?: string }
): Promise<{ notes: NoteListItem[]; total: number }>

// GET /api/v1/notes/{noteId}
export function getNote(noteId: string): Promise<Note>

// POST /api/v1/notes
export function createNote(input: NoteCreateInput): Promise<Note>

// PATCH /api/v1/notes/{noteId}
export function updateNote(noteId: string, input: NoteUpdateInput): Promise<Note>

// DELETE /api/v1/notes/{noteId}
export function deleteNote(noteId: string): Promise<void>

// POST /api/v1/notes/{noteId}/documents  body: { document_id }
export function addNoteDocument(noteId: string, documentId: string): Promise<void>

// DELETE /api/v1/notes/{noteId}/documents/{documentId}
export function removeNoteDocument(noteId: string, documentId: string): Promise<void>

// GET /api/v1/notes/{noteId}/documents
export function getNoteDocuments(noteId: string): Promise<{ documents: NoteDocumentTag[] }>
```

### 4.2 marks.ts

```typescript
// GET /api/v1/documents/{documentId}/marks
export function listMarksByDocument(documentId: string): Promise<{ marks: Mark[]; total: number }>

// GET /api/v1/notebooks/{notebookId}/marks
export function listMarksByNotebook(notebookId: string): Promise<{ marks: Mark[]; total: number }>

// POST /api/v1/documents/{documentId}/marks
export function createMark(documentId: string, input: MarkCreateInput): Promise<Mark>

// DELETE /api/v1/marks/{markId}
export function deleteMark(markId: string): Promise<void>
```

### 4.3 chat.ts 扩展

```typescript
// POST /api/v1/chat/confirm
export function confirmAction(params: {
  session_id: string;
  request_id: string;
  approved: boolean;
}): Promise<void>
```

## 5. Query Key 一览

| Query Key | 对应 API | 刷新时机 |
|-----------|---------|---------|
| ["notes", notebookId, docFilter] | GET /notebooks/{id}/notes | 创建/删除 note、变更文档关联 |
| ["note", noteId] | GET /notes/{id} | 更新 note 内容 |
| ["note-documents", noteId] | GET /notes/{id}/documents | 添加/移除文档关联 |
| ["marks", "document", documentId] | GET /documents/{id}/marks | 创建 mark（Reader 用） |
| ["marks", "notebook", notebookId] | GET /notebooks/{id}/marks | 创建 mark（Studio 用） |

注意：创建 mark 后需同时 invalidate document 级和 notebook 级的 marks query。
