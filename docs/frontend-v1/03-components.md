# 核心组件设计

## 1. 概述

本文档描述MediMind Agent前端的核心组件设计,包括文档列表、文档阅读器、文本选中菜单和聊天组件。

---

## 2. Sources面板组件

### 2.1 SourcesPanel

左侧面板容器,在文档列表和文档阅读器之间切换。

```typescript
// components/sources/sources-panel.tsx

interface SourcesPanelProps {
  notebookId: string;
}

export function SourcesPanel({ notebookId }: SourcesPanelProps) {
  const { currentDocument } = useReaderStore();

  return (
    <div className="h-full flex flex-col">
      {currentDocument ? (
        <DocumentReader />
      ) : (
        <SourceList notebookId={notebookId} />
      )}
    </div>
  );
}
```

### 2.2 SourceList

文档列表组件。

```typescript
// components/sources/source-list.tsx

interface SourceListProps {
  notebookId: string;
}

export function SourceList({ notebookId }: SourceListProps) {
  const { data: documents, isLoading } = useNotebookDocuments(notebookId);

  return (
    <div className="flex flex-col h-full">
      {/* 头部 */}
      <div className="p-4 border-b">
        <h2 className="text-lg font-semibold">Sources</h2>
        <AddSourceDialog notebookId={notebookId}>
          <Button variant="outline" className="w-full mt-2">
            <Plus className="w-4 h-4 mr-2" />
            Add sources
          </Button>
        </AddSourceDialog>
      </div>

      {/* 文档列表 */}
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-2">
          {isLoading && <SourceCardSkeleton count={3} />}
          {documents?.map((doc) => (
            <SourceCard key={doc.document_id} document={doc} />
          ))}
          {documents?.length === 0 && (
            <p className="text-muted-foreground text-center py-8">
              还没有文档,点击上方按钮添加
            </p>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
```

### 2.3 SourceCard

单个文档卡片。

```typescript
// components/sources/source-card.tsx

interface SourceCardProps {
  document: Document;
}

export function SourceCard({ document }: SourceCardProps) {
  const { openDocument } = useReaderStore();
  const deleteMutation = useDeleteDocument();

  const handleView = () => {
    openDocument(document);
  };

  return (
    <Card className="p-3">
      <div className="flex items-start gap-3">
        {/* 图标 */}
        <div className="p-2 rounded bg-muted">
          <FileIcon type={document.content_type} />
        </div>

        {/* 信息 */}
        <div className="flex-1 min-w-0">
          <h3 className="font-medium truncate">{document.title}</h3>
          <p className="text-sm text-muted-foreground">
            {formatFileSize(document.file_size)}
          </p>
          {document.status === 'processing' && (
            <Badge variant="secondary">处理中...</Badge>
          )}
        </div>

        {/* 操作按钮 */}
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleView}
            disabled={document.status !== 'completed'}
          >
            View
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon">
                <MoreVertical className="w-4 h-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem onClick={() => deleteMutation.mutate(document.document_id)}>
                <Trash className="w-4 h-4 mr-2" />
                删除
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </Card>
  );
}
```

---

## 3. 文档阅读器组件

### 3.1 DocumentReader

文档阅读器容器。

```typescript
// components/reader/document-reader.tsx

export function DocumentReader() {
  const { currentDocument, closeDocument } = useReaderStore();
  const { data: content, isLoading } = useDocumentContent(
    currentDocument?.document_id ?? null
  );

  if (!currentDocument) return null;

  return (
    <div className="h-full flex flex-col">
      {/* 头部 */}
      <div className="p-4 border-b flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={closeDocument}>
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <h2 className="font-semibold truncate">{currentDocument.title}</h2>
        </div>
        {content?.original_file_available && (
          <Button variant="outline" size="sm" asChild>
            <a href={content.download_url} download>
              <Download className="w-4 h-4 mr-2" />
              下载
            </a>
          </Button>
        )}
      </div>

      {/* 内容区域 */}
      <ScrollArea className="flex-1">
        <div className="p-6">
          {isLoading && <ReaderSkeleton />}
          {content && (
            <MarkdownViewer
              content={content.content}
              documentId={currentDocument.document_id}
            />
          )}
        </div>
      </ScrollArea>

      {/* 选中菜单 */}
      <SelectionMenu />
    </div>
  );
}
```

### 3.2 MarkdownViewer

Markdown渲染组件,支持文本选中。

```typescript
// components/reader/markdown-viewer.tsx

interface MarkdownViewerProps {
  content: string;
  documentId: string;
}

export function MarkdownViewer({ content, documentId }: MarkdownViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // 文本选中hook
  useTextSelection(containerRef, documentId);

  return (
    <div
      ref={containerRef}
      className="prose prose-slate dark:prose-invert max-w-none"
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={markdownComponents}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

// Markdown组件映射
const markdownComponents = {
  h1: ({ children }) => (
    <h1 className="text-2xl font-bold mt-8 mb-4 first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-xl font-semibold mt-6 mb-3">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-lg font-semibold mt-5 mb-2">{children}</h3>
  ),
  p: ({ children }) => (
    <p className="mb-4 leading-relaxed text-base">{children}</p>
  ),
  ul: ({ children }) => (
    <ul className="list-disc pl-6 mb-4 space-y-1">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal pl-6 mb-4 space-y-1">{children}</ol>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto mb-4">
      <table className="min-w-full border-collapse border">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border px-3 py-2 bg-muted font-semibold text-left">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border px-3 py-2">{children}</td>
  ),
  code: ({ inline, children, className }) => {
    if (inline) {
      return (
        <code className="bg-muted px-1.5 py-0.5 rounded text-sm">
          {children}
        </code>
      );
    }
    return (
      <pre className="bg-muted p-4 rounded-lg overflow-x-auto mb-4">
        <code className={className}>{children}</code>
      </pre>
    );
  },
  blockquote: ({ children }) => (
    <blockquote className="border-l-4 border-primary pl-4 italic my-4">
      {children}
    </blockquote>
  ),
};
```

### 3.3 useTextSelection Hook

文本选中检测hook。

```typescript
// lib/hooks/use-text-selection.ts

export function useTextSelection(
  containerRef: RefObject<HTMLElement>,
  documentId: string
) {
  const { setSelection, showMenu, hideMenu } = useReaderStore();

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleMouseUp = (event: MouseEvent) => {
      const selection = window.getSelection();

      if (!selection || selection.isCollapsed) {
        hideMenu();
        setSelection(null);
        return;
      }

      const selectedText = selection.toString().trim();
      if (!selectedText || selectedText.length < 2) {
        hideMenu();
        setSelection(null);
        return;
      }

      // 确保选中的内容在容器内
      const range = selection.getRangeAt(0);
      if (!container.contains(range.commonAncestorContainer)) {
        return;
      }

      // 设置选中状态
      setSelection({
        documentId,
        selectedText,
      });

      // 显示菜单
      showMenu({
        x: event.clientX,
        y: event.clientY,
      });
    };

    container.addEventListener('mouseup', handleMouseUp);
    return () => container.removeEventListener('mouseup', handleMouseUp);
  }, [containerRef, documentId, setSelection, showMenu, hideMenu]);
}
```

### 3.4 SelectionMenu

选中文本后的操作菜单。

```typescript
// components/reader/selection-menu.tsx

export function SelectionMenu() {
  const { selection, isMenuVisible, menuPosition, hideMenu } = useReaderStore();
  const { sendWithContext } = useChatActions();

  if (!isMenuVisible || !menuPosition || !selection) {
    return null;
  }

  const handleAction = async (mode: 'explain' | 'conclude') => {
    hideMenu();

    // 高亮选中文本
    highlightSelection();

    // 发送消息
    const defaultMessage = mode === 'explain' ? '请解释这段内容' : '请总结这段内容';
    await sendWithContext(defaultMessage, mode, {
      document_id: selection.documentId,
      selected_text: selection.selectedText,
    });
  };

  return (
    <div
      className="fixed z-50 bg-popover border rounded-lg shadow-lg p-1 flex gap-1"
      style={{
        left: menuPosition.x,
        top: menuPosition.y + 10,
      }}
    >
      <Button
        variant="ghost"
        size="sm"
        onClick={() => handleAction('explain')}
      >
        <Lightbulb className="w-4 h-4 mr-1" />
        Explain
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => handleAction('conclude')}
      >
        <FileText className="w-4 h-4 mr-1" />
        Conclude
      </Button>
    </div>
  );
}

// 高亮选中文本
function highlightSelection() {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed) return;

  const range = selection.getRangeAt(0);
  const span = document.createElement('span');
  span.className = 'bg-yellow-200 dark:bg-yellow-900/50';
  range.surroundContents(span);

  selection.removeAllRanges();
}
```

---

## 4. 聊天组件

### 4.1 ChatPanel

聊天面板容器。

```typescript
// components/chat/chat-panel.tsx

interface ChatPanelProps {
  notebookId: string;
}

export function ChatPanel({ notebookId }: ChatPanelProps) {
  const { messages, currentMode, setMode } = useChatStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  // 自动滚动到底部
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="h-full flex flex-col">
      {/* 头部: 模式切换 */}
      <div className="p-4 border-b">
        <Tabs value={currentMode} onValueChange={(v) => setMode(v as 'chat' | 'ask')}>
          <TabsList>
            <TabsTrigger value="chat">Chat</TabsTrigger>
            <TabsTrigger value="ask">Ask</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* 消息列表 */}
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-4">
          {messages.length === 0 && <WelcomeMessage />}
          {messages.map((message) => (
            <MessageItem key={message.id} message={message} />
          ))}
          <div ref={scrollRef} />
        </div>
      </ScrollArea>

      {/* 输入框 */}
      <ChatInput notebookId={notebookId} />
    </div>
  );
}
```

### 4.2 MessageItem

单条消息组件。

```typescript
// components/chat/message-item.tsx

interface MessageItemProps {
  message: Message;
}

export function MessageItem({ message }: MessageItemProps) {
  const isUser = message.role === 'user';

  return (
    <div className={cn('flex gap-3', isUser && 'flex-row-reverse')}>
      {/* 头像 */}
      <div
        className={cn(
          'w-8 h-8 rounded-full flex items-center justify-center',
          isUser ? 'bg-primary' : 'bg-muted'
        )}
      >
        {isUser ? (
          <User className="w-4 h-4 text-primary-foreground" />
        ) : (
          <Bot className="w-4 h-4" />
        )}
      </div>

      {/* 内容 */}
      <div className={cn('flex-1 max-w-[80%]', isUser && 'text-right')}>
        <Card className={cn('p-4', isUser && 'bg-primary text-primary-foreground')}>
          {/* 模式标签 */}
          {!isUser && message.mode !== 'chat' && (
            <Badge variant="secondary" className="mb-2">
              {message.mode}
            </Badge>
          )}

          {/* 消息内容 */}
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        </Card>

        {/* Sources */}
        {message.sources && message.sources.length > 0 && (
          <SourcesCard sources={message.sources} className="mt-2" />
        )}
      </div>
    </div>
  );
}
```

### 4.3 SourcesCard

来源引用卡片。

```typescript
// components/chat/sources-card.tsx

interface SourcesCardProps {
  sources: Source[];
  className?: string;
}

export function SourcesCard({ sources, className }: SourcesCardProps) {
  const { openDocument } = useReaderStore();
  const { data: documents } = useNotebookDocuments();

  // 根据document_id查找文档信息
  const getDocumentTitle = (documentId: string) => {
    return documents?.find((d) => d.document_id === documentId)?.title || '未知文档';
  };

  return (
    <Card className={cn('p-3', className)}>
      <p className="text-sm font-medium mb-2">引用来源</p>
      <div className="space-y-1">
        {sources.slice(0, 3).map((source, index) => (
          <button
            key={source.chunk_id}
            className="w-full text-left p-2 rounded hover:bg-muted transition-colors"
            onClick={() => {
              const doc = documents?.find((d) => d.document_id === source.document_id);
              if (doc) openDocument(doc);
            }}
          >
            <p className="text-sm font-medium">
              [{index + 1}] {getDocumentTitle(source.document_id)}
            </p>
            <p className="text-xs text-muted-foreground line-clamp-2">
              {source.text}
            </p>
          </button>
        ))}
      </div>
    </Card>
  );
}
```

### 4.4 ChatInput

聊天输入框。

```typescript
// components/chat/chat-input.tsx

interface ChatInputProps {
  notebookId: string;
}

export function ChatInput({ notebookId }: ChatInputProps) {
  const [input, setInput] = useState('');
  const { isStreaming, currentMode } = useChatStore();
  const { sendMessage } = useChatActions();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    await sendMessage(input, currentMode);
    setInput('');
  };

  return (
    <form onSubmit={handleSubmit} className="p-4 border-t">
      <div className="flex gap-2">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入消息..."
          className="min-h-[60px] resize-none"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSubmit(e);
            }
          }}
        />
        <Button type="submit" disabled={!input.trim() || isStreaming}>
          {isStreaming ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
        </Button>
      </div>
    </form>
  );
}
```

### 4.5 useChatActions Hook

聊天操作hook。

```typescript
// lib/hooks/use-chat-actions.ts

export function useChatActions() {
  const { addMessage, setStreaming, appendStreamContent } = useChatStore();
  const { currentSessionId } = useNotebookStore();
  const notebookId = useParams().id as string;

  const sendMessage = async (
    message: string,
    mode: 'chat' | 'ask',
    context?: { document_id: string; selected_text: string }
  ) => {
    if (!currentSessionId) return;

    // 添加用户消息
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: message,
      mode,
      timestamp: new Date(),
    };
    addMessage(userMessage);

    // 开始流式响应
    setStreaming(true);
    const assistantMessageId = crypto.randomUUID();

    try {
      const stream = streamChat(
        notebookId,
        message,
        mode,
        currentSessionId,
        context
      );

      let fullContent = '';
      let sources: Source[] = [];

      for await (const event of stream) {
        if (event.type === 'content') {
          fullContent += event.delta;
          appendStreamContent(event.delta);
        } else if (event.type === 'sources') {
          sources = event.sources;
        }
      }

      // 添加助手消息
      addMessage({
        id: assistantMessageId,
        role: 'assistant',
        content: fullContent,
        mode,
        sources,
        timestamp: new Date(),
      });
    } finally {
      setStreaming(false);
    }
  };

  const sendWithContext = async (
    message: string,
    mode: 'explain' | 'conclude',
    context: { document_id: string; selected_text: string }
  ) => {
    return sendMessage(message, mode as any, context);
  };

  return { sendMessage, sendWithContext };
}
```

---

## 5. 组件样式规范

### 5.1 间距

| 场景 | 间距 |
|------|------|
| 面板内边距 | p-4 |
| 卡片内边距 | p-3 |
| 元素间距 | space-y-2 或 gap-2 |
| 段落间距 | mb-4 |

### 5.2 字体

| 场景 | 类名 |
|------|------|
| 面板标题 | text-lg font-semibold |
| 卡片标题 | font-medium |
| 正文 | text-base |
| 辅助文字 | text-sm text-muted-foreground |

### 5.3 颜色

使用shadcn/ui的CSS变量,自动适应深色模式:

| 用途 | 变量 |
|------|------|
| 背景 | bg-background |
| 卡片 | bg-card |
| 强调 | bg-muted |
| 主色 | bg-primary |
| 文字 | text-foreground |
| 次要文字 | text-muted-foreground |
