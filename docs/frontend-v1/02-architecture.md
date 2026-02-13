# 前端架构设计

## 1. 概述

本文档描述Newbee Notebook前端的整体架构设计,包括页面布局、数据流和状态管理。

---

## 2. 页面布局

### 2.1 三列布局

```
+------------------------------------------------------------------+
|  Header: MediMind - {Notebook标题}            [Settings] [Share]  |
+------------------+------------------------+----------------------+
|                  |                        |                      |
|    Sources       |         Chat           |       Studio         |
|    Panel         |        Panel           |       Panel          |
|                  |                        |                      |
|   [+ Add]        |   消息列表              |   [Audio Overview]   |
|                  |                        |   [Mind Map]         |
|   文档1          |   AI回复...            |   [Flashcards]       |
|   [View]         |                        |   ...                |
|                  |   推荐问题:             |                      |
|   文档2          |   - 问题1              |   ---------------    |
|   [View]         |   - 问题2              |                      |
|                  |                        |   Notes              |
|   ...            |   +---------------+    |   - Note 1           |
|                  |   | 输入框...     |    |   - Note 2           |
|                  |   +---------------+    |   [+ Add note]       |
|                  |                        |                      |
+------------------+------------------------+----------------------+
     可伸缩                主区域                  可伸缩
```

### 2.2 布局组件结构

```
AppShell
├── Header
│   ├── Logo
│   ├── NotebookTitle
│   └── Actions (Settings, Share)
└── MainContent
    └── ResizablePanelGroup (horizontal)
        ├── ResizablePanel (Sources)
        │   ├── SourceList (default)
        │   └── DocumentReader (when viewing)
        ├── ResizableHandle
        ├── ResizablePanel (Chat)
        │   └── ChatPanel
        ├── ResizableHandle
        └── ResizablePanel (Studio)
            └── StudioPanel (placeholder)
```

### 2.3 面板尺寸

| 面板 | 默认宽度 | 最小宽度 | 可折叠 |
|------|----------|----------|--------|
| Sources | 25% | 200px | 是 |
| Chat | 50% | 400px | 否 |
| Studio | 25% | 200px | 是 |

---

## 3. 页面路由

```
/                           # 首页,重定向到notebooks
/notebooks                  # Notebook列表
/notebooks/[id]             # Notebook详情(三列布局)
/library                    # Library管理页面
```

### 3.1 路由组件

```typescript
// app/notebooks/[id]/page.tsx

export default async function NotebookPage({
  params,
}: {
  params: { id: string };
}) {
  return (
    <NotebookProvider notebookId={params.id}>
      <AppShell>
        <ResizablePanelGroup direction="horizontal">
          <SourcesPanel />
          <ChatPanel />
          <StudioPanel />
        </ResizablePanelGroup>
      </AppShell>
    </NotebookProvider>
  );
}
```

---

## 4. 状态管理

### 4.1 Store设计

```typescript
// stores/notebook-store.ts

interface NotebookState {
  // 数据
  notebook: Notebook | null;
  documents: Document[];
  sessions: Session[];
  currentSessionId: string | null;

  // 状态
  isLoading: boolean;
  error: string | null;

  // Actions
  setNotebook: (notebook: Notebook) => void;
  setDocuments: (documents: Document[]) => void;
  addDocument: (document: Document) => void;
  removeDocument: (documentId: string) => void;
  setCurrentSession: (sessionId: string) => void;
}

export const useNotebookStore = create<NotebookState>((set) => ({
  notebook: null,
  documents: [],
  sessions: [],
  currentSessionId: null,
  isLoading: false,
  error: null,

  setNotebook: (notebook) => set({ notebook }),
  setDocuments: (documents) => set({ documents }),
  addDocument: (document) =>
    set((state) => ({ documents: [...state.documents, document] })),
  removeDocument: (documentId) =>
    set((state) => ({
      documents: state.documents.filter((d) => d.document_id !== documentId),
    })),
  setCurrentSession: (sessionId) => set({ currentSessionId: sessionId }),
}));
```

```typescript
// stores/reader-store.ts

interface ReaderState {
  // 当前查看的文档
  currentDocument: Document | null;
  documentContent: string | null;

  // 选中状态
  selection: SelectionContext | null;
  isMenuVisible: boolean;
  menuPosition: { x: number; y: number } | null;

  // Actions
  openDocument: (document: Document) => void;
  closeDocument: () => void;
  setDocumentContent: (content: string) => void;
  setSelection: (selection: SelectionContext | null) => void;
  showMenu: (position: { x: number; y: number }) => void;
  hideMenu: () => void;
}

interface SelectionContext {
  documentId: string;
  selectedText: string;
}

export const useReaderStore = create<ReaderState>((set) => ({
  currentDocument: null,
  documentContent: null,
  selection: null,
  isMenuVisible: false,
  menuPosition: null,

  openDocument: (document) => set({ currentDocument: document }),
  closeDocument: () =>
    set({ currentDocument: null, documentContent: null, selection: null }),
  setDocumentContent: (content) => set({ documentContent: content }),
  setSelection: (selection) => set({ selection }),
  showMenu: (position) => set({ isMenuVisible: true, menuPosition: position }),
  hideMenu: () => set({ isMenuVisible: false, menuPosition: null }),
}));
```

```typescript
// stores/chat-store.ts

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  mode: 'chat' | 'ask' | 'explain' | 'conclude';
  sources?: Source[];
  timestamp: Date;
}

interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  currentMode: 'chat' | 'ask';
  streamingContent: string;

  // Actions
  addMessage: (message: Message) => void;
  updateMessage: (id: string, content: string) => void;
  setStreaming: (isStreaming: boolean) => void;
  appendStreamContent: (chunk: string) => void;
  setMode: (mode: 'chat' | 'ask') => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isStreaming: false,
  currentMode: 'chat',
  streamingContent: '',

  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  updateMessage: (id, content) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === id ? { ...m, content } : m
      ),
    })),
  setStreaming: (isStreaming) => set({ isStreaming }),
  appendStreamContent: (chunk) =>
    set((state) => ({ streamingContent: state.streamingContent + chunk })),
  setMode: (mode) => set({ currentMode: mode }),
  clearMessages: () => set({ messages: [], streamingContent: '' }),
}));
```

### 4.2 数据获取

使用TanStack Query管理服务端状态:

```typescript
// lib/hooks/use-notebook.ts

export function useNotebook(notebookId: string) {
  return useQuery({
    queryKey: ['notebook', notebookId],
    queryFn: () => fetchNotebook(notebookId),
  });
}

export function useNotebookDocuments(notebookId: string) {
  return useQuery({
    queryKey: ['documents', notebookId],
    queryFn: () => fetchNotebookDocuments(notebookId),
  });
}

export function useDocumentContent(documentId: string | null) {
  return useQuery({
    queryKey: ['document-content', documentId],
    queryFn: () => documentId ? fetchDocumentContent(documentId) : null,
    enabled: !!documentId,
  });
}
```

---

## 5. 数据流

### 5.1 文档查看流程

```
用户点击View按钮
    |
    v
useReaderStore.openDocument(document)
    |
    v
左侧面板切换为DocumentReader
    |
    v
useDocumentContent(documentId) 获取内容
    |
    v
MarkdownViewer 渲染内容
```

### 5.2 文本选中流程

```
用户在MarkdownViewer中选中文字
    |
    v
useTextSelection hook 检测选中
    |
    v
useReaderStore.setSelection({ documentId, selectedText })
    |
    v
useReaderStore.showMenu({ x, y })
    |
    v
SelectionMenu 显示在鼠标位置
    |
    v
用户点击 Explain 或 Conclude
    |
    v
sendMessage(mode, selectedText)
    |
    v
ChatPanel 显示响应
```

### 5.3 聊天流程

```
用户输入消息并发送
    |
    v
useChatStore.addMessage(userMessage)
    |
    v
useChatStream.send(message, mode, context)
    |
    v
SSE流式接收响应
    |
    v
useChatStore.appendStreamContent(chunk)
    |
    v
流结束后 useChatStore.addMessage(assistantMessage)
    |
    v
MessageList 更新显示
```

---

## 6. API层设计

### 6.1 API模块

```typescript
// lib/api/documents.ts

const API_BASE = '/api/v1';

export async function fetchNotebookDocuments(notebookId: string) {
  const response = await fetch(
    `${API_BASE}/documents/notebooks/${notebookId}`
  );
  if (!response.ok) throw new Error('Failed to fetch documents');
  return response.json();
}

export async function fetchDocumentContent(documentId: string) {
  const response = await fetch(
    `${API_BASE}/documents/${documentId}/content?format=markdown`
  );
  if (!response.ok) throw new Error('Failed to fetch document content');
  return response.json();
}

export async function uploadDocument(notebookId: string, file: File) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(
    `${API_BASE}/documents/notebooks/${notebookId}/upload`,
    {
      method: 'POST',
      body: formData,
    }
  );
  if (!response.ok) throw new Error('Failed to upload document');
  return response.json();
}
```

```typescript
// lib/api/chat.ts

export async function* streamChat(
  notebookId: string,
  message: string,
  mode: string,
  sessionId: string,
  context?: { document_id: string; selected_text: string }
): AsyncGenerator<ChatEvent> {
  const response = await fetch(
    `${API_BASE}/chat/notebooks/${notebookId}/chat/stream`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify({
        message,
        mode,
        session_id: sessionId,
        context,
      }),
    }
  );

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader!.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        // event type
      } else if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        yield data;
      }
    }
  }
}
```

---

## 7. 错误处理

### 7.1 全局错误边界

```typescript
// components/error-boundary.tsx

'use client';

import { useEffect } from 'react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center h-full">
      <h2 className="text-xl font-semibold mb-4">出错了</h2>
      <p className="text-muted-foreground mb-4">{error.message}</p>
      <button onClick={reset} className="btn btn-primary">
        重试
      </button>
    </div>
  );
}
```

### 7.2 API错误处理

```typescript
// lib/api/utils.ts

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(
      data.detail || 'Request failed',
      response.status,
      data.detail
    );
  }
  return response.json();
}
```

---

## 8. 性能优化

### 8.1 代码分割

```typescript
// 动态导入重量级组件
const MarkdownViewer = dynamic(
  () => import('@/components/reader/markdown-viewer'),
  { loading: () => <Skeleton className="h-full" /> }
);
```

### 8.2 虚拟滚动

对于长消息列表,使用虚拟滚动:

```typescript
// 使用 @tanstack/react-virtual
import { useVirtualizer } from '@tanstack/react-virtual';
```

### 8.3 防抖

文本选中事件使用防抖:

```typescript
const handleSelectionChange = useDebouncedCallback(
  (selection: Selection) => {
    // 处理选中
  },
  200
);
```

---

## 9. 响应式设计

### 9.1 断点

| 断点 | 宽度 | 布局 |
|------|------|------|
| sm | < 640px | 单列,Tab切换 |
| md | 640-1024px | 两列,隐藏Studio |
| lg | > 1024px | 三列完整布局 |

### 9.2 移动端适配

```typescript
// hooks/use-media-query.ts

export function useIsDesktop() {
  return useMediaQuery('(min-width: 1024px)');
}

// 组件中使用
const isDesktop = useIsDesktop();

return isDesktop ? (
  <ResizablePanelGroup>{/* 三列布局 */}</ResizablePanelGroup>
) : (
  <Tabs>{/* Tab切换 */}</Tabs>
);
```
