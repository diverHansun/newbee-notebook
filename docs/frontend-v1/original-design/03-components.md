# 核心组件设计

## 1. 概述

本文档描述 Newbee Notebook 前端的核心组件设计，包括文档列表、文档阅读器、文本选中菜单、聊天组件和 ExplainCard。各模块的详细设计见 `plan-1/` 目录下的对应文档。

---

## 2. Sources 面板组件

### 2.1 SourcesPanel

左侧面板容器，在文档列表和文档阅读器之间切换。

```typescript
// components/sources/sources-panel.tsx

interface SourcesPanelProps {
  notebookId: string;
}

export function SourcesPanel({ notebookId }: SourcesPanelProps) {
  const { currentDocumentId } = useReaderStore();

  return (
    <div className="h-full flex flex-col">
      {currentDocumentId ? (
        <DocumentReader documentId={currentDocumentId} />
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
              还没有文档，点击上方按钮添加
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

  return (
    <Card className="p-3">
      <div className="flex items-start gap-3">
        <div className="p-2 rounded bg-muted">
          <FileIcon type={document.content_type} />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-medium truncate">{document.title}</h3>
          <p className="text-sm text-muted-foreground">
            {formatFileSize(document.file_size)}
          </p>
          {document.status === 'processing' && (
            <Badge variant="secondary">处理中...</Badge>
          )}
        </div>
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => openDocument(document.document_id)}
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
              <DropdownMenuItem
                onClick={() => deleteMutation.mutate(document.document_id)}
              >
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

文档阅读器容器。从 Main Panel 的 Reader View 中使用。

```typescript
// components/reader/document-reader.tsx

interface DocumentReaderProps {
  documentId: string;
}

export function DocumentReader({ documentId }: DocumentReaderProps) {
  const { closeDocument } = useReaderStore();
  const { data: document } = useDocument(documentId);
  const { data: content, isLoading } = useDocumentContent(documentId);

  return (
    <div className="h-full flex flex-col">
      {/* 头部 */}
      <div className="p-4 border-b flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={closeDocument}>
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <h2 className="font-semibold truncate">{document?.title}</h2>
        </div>
      </div>

      {/* 内容区域 */}
      <ScrollArea className="flex-1">
        <div className="p-6">
          {isLoading && <ReaderSkeleton />}
          {content && (
            <MarkdownViewer content={content.content} />
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

Markdown 渲染组件。使用 unified/remark/rehype 管线，而非 react-markdown。

```typescript
// components/reader/MarkdownViewer.tsx

interface MarkdownViewerProps {
  content: string;
  className?: string;
}

export function MarkdownViewer({ content, className }: MarkdownViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // 通过 unified 管线将 Markdown 转为 React 元素
  const renderedContent = useMemo(
    () => renderMarkdown(content),
    [content]
  );

  return (
    <div
      ref={containerRef}
      className={cn('markdown-content', className)}
    >
      {renderedContent}
    </div>
  );
}
```

管线配置封装在 `markdown-pipeline.ts` 中：

```typescript
// components/reader/markdown-pipeline.ts

import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import remarkCjkFriendly from 'remark-cjk-friendly';
import remarkRehype from 'remark-rehype';
import rehypeSlug from 'rehype-slug';
import rehypeHighlight from 'rehype-highlight';
import rehypeKatex from 'rehype-katex';
import rehypeReact from 'rehype-react';
export function renderMarkdown(content: string) {
  const processor = unified()
    .use(remarkParse)
    .use(remarkGfm)
    .use(remarkMath)
    .use(remarkCjkFriendly)
    .use(remarkRehype)
    .use(rehypeSlug)
    .use(rehypeHighlight)
    .use(rehypeKatex)
    .use(rehypeReact, { /* React createElement 配置 */ });

  return processor.processSync(content).result;
}
```

无需自定义插件处理图片路径。后端在文档处理保存阶段（`save_markdown()` 函数）已将 MinerU 输出的相对图片路径转换为 API 绝对路径（`/api/v1/documents/{id}/assets/images/{hash}.jpg`），前端管线直接解析即可。

Markdown 内容区域的排版样式由独立的 CSS 文件（`styles/markdown-content.css`）控制，借鉴 VS Code / Cursor 的 Markdown Preview 风格。使用 CSS 变量响应 light/dark 主题切换。长文档使用 `content-visibility: auto` 优化渲染性能。

详细设计见 `plan-1/01-markdown-viewer/` 文档。

### 3.3 useTextSelection Hook

文本选中检测 hook。使用 200ms 防抖，基于 Selection API 获取选中文本和位置信息。

```typescript
// lib/hooks/useTextSelection.ts

export function useTextSelection(
  containerRef: RefObject<HTMLElement>,
  documentId: string
) {
  const { setSelection, showMenu, hideMenu } = useReaderStore();

  // 返回值
  // selection: { text, documentId } | null
  // menuPosition: { top, left }
  // showMenu: boolean
  // clearSelection: () => void
}
```

hook 内部监听 `selectionchange` 事件，200ms 防抖后判断选中内容是否有效（非空、在容器内），计算菜单位置（选中区域上方，空间不足则在下方），更新 reader-store。

详细设计见 `plan-1/05-text-selection.md`。

### 3.4 SelectionMenu

选中文本后的浮动操作菜单。包含"解释"和"总结"两个按钮。

```typescript
// components/reader/SelectionMenu.tsx

export function SelectionMenu() {
  const { selection, isMenuVisible, menuPosition, hideMenu } = useReaderStore();
  const { sendMessage } = useChatSession();

  if (!isMenuVisible || !menuPosition || !selection) return null;

  const handleAction = (mode: 'explain' | 'conclude') => {
    hideMenu();
    sendMessage(
      mode === 'explain' ? '请解释这段内容' : '请总结这段内容',
      mode,
      {
        document_id: selection.documentId,
        selected_text: selection.selectedText,
      }
    );
  };

  return (
    <div
      className="fixed z-50 bg-popover border rounded-lg shadow-lg p-1 flex gap-1"
      style={{ left: menuPosition.left, top: menuPosition.top }}
    >
      <Button variant="ghost" size="sm" onClick={() => handleAction('explain')}>
        <Lightbulb className="w-4 h-4 mr-1" />
        解释
      </Button>
      <Button variant="ghost" size="sm" onClick={() => handleAction('conclude')}>
        <FileText className="w-4 h-4 mr-1" />
        总结
      </Button>
    </div>
  );
}
```

点击后通过 `useChatSession.sendMessage` 以 explain/conclude 模式发送消息，回复展示在 ExplainCard 浮动卡片中（而非主聊天面板）。菜单在以下情况自动关闭：点击菜单外区域、选中内容消失、页面滚动。

---

## 4. 聊天组件

### 4.1 ChatPanel

主聊天面板，处理 chat/ask 模式的消息。

```typescript
// components/chat/ChatPanel.tsx

interface ChatPanelProps {
  notebookId: string;
}

export function ChatPanel({ notebookId }: ChatPanelProps) {
  const { messages, isStreaming } = useChatStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  return (
    <div className="h-full flex flex-col">
      {/* 头部: Session 选择器 */}
      <div className="p-4 border-b flex items-center justify-between">
        <SessionSelector notebookId={notebookId} />
        <Button variant="outline" size="sm">
          <Plus className="w-4 h-4 mr-1" />
          新建会话
        </Button>
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

      {/* 输入框（左侧含 chat/ask 模式切换） */}
      <ChatInput notebookId={notebookId} />
    </div>
  );
}
```

ChatPanel 只展示 chat/ask 模式的消息。explain/conclude 的回复由 ExplainCard 独立展示。

### 4.2 MessageItem

单条消息渲染。AI 回复内容通过 MarkdownViewer 渲染，流式进行中显示打字光标效果。

```typescript
// components/chat/MessageItem.tsx

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
          {!isUser && message.mode !== 'chat' && (
            <Badge variant="secondary" className="mb-2">{message.mode}</Badge>
          )}
          <div className="markdown-content">
            {isUser ? (
              <p>{message.content}</p>
            ) : (
              <MarkdownViewer content={message.content} />
            )}
          </div>
        </Card>

        {/* 来源引用 */}
        {message.sources && message.sources.length > 0 && (
          <SourcesCard sources={message.sources} className="mt-2" />
        )}
      </div>
    </div>
  );
}
```

AI 消息的 Markdown 渲染复用 MarkdownViewer 组件，保持渲染风格一致。

### 4.3 SourcesCard

AI 消息附带的来源引用展示。列出引用的文档标题，点击可跳转到对应文档。

```typescript
// components/chat/SourcesCard.tsx

interface SourcesCardProps {
  sources: Source[];
  className?: string;
}

export function SourcesCard({ sources, className }: SourcesCardProps) {
  const { openDocument } = useReaderStore();

  return (
    <Card className={cn('p-3', className)}>
      <p className="text-sm font-medium mb-2">引用来源</p>
      <div className="space-y-1">
        {sources.slice(0, 3).map((source, index) => (
          <button
            key={source.chunk_id}
            className="w-full text-left p-2 rounded hover:bg-muted transition-colors"
            onClick={() => openDocument(source.document_id)}
          >
            <p className="text-sm font-medium">
              [{index + 1}] {source.document_title}
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

### 4.4 ExplainCard

explain/conclude 模式的浮动卡片。独立于主聊天面板，可拖动、可调整大小、可折叠。

```typescript
// components/chat/ExplainCard.tsx

interface ExplainCardProps {
  visible: boolean;
  content: string;
  isStreaming: boolean;
  selectedText: string;
  mode: 'explain' | 'conclude';
  onClose: () => void;
}

export function ExplainCard({
  visible,
  content,
  isStreaming,
  selectedText,
  mode,
  onClose,
}: ExplainCardProps) {
  if (!visible) return null;

  return (
    <div className="fixed z-40 /* 拖动 + 缩放逻辑 */">
      <Card className="w-[400px] max-h-[500px] flex flex-col shadow-xl">
        {/* 标题栏：可拖动 */}
        <div className="p-3 border-b flex items-center justify-between cursor-move">
          <div className="flex items-center gap-2">
            <Badge variant="secondary">
              {mode === 'explain' ? '解释' : '总结'}
            </Badge>
            <span className="text-sm text-muted-foreground truncate max-w-[200px]">
              {selectedText}
            </span>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* 内容区域 */}
        <ScrollArea className="flex-1 p-4">
          <div className="markdown-content">
            <MarkdownViewer content={content} />
          </div>
          {isStreaming && <TypingCursor />}
        </ScrollArea>
      </Card>
    </div>
  );
}
```

ExplainCard 的数据来源于 chat-store 的 `explainCard` 字段，由 useChatSession hook 在接收 explain/conclude 模式的 SSE 事件时更新。关闭卡片后，explainCard 状态清空。

详细设计见 `plan-1/02-chat-system/` 文档。

### 4.5 ChatInput

聊天输入框。支持 Enter 发送、Shift+Enter 换行。流式响应进行中时显示取消按钮。

```typescript
// components/chat/ChatInput.tsx

interface ChatInputProps {
  notebookId: string;
}

export function ChatInput({ notebookId }: ChatInputProps) {
  const [input, setInput] = useState('');
  const { isStreaming, currentMode } = useChatStore();
  const { sendMessage, cancelStream } = useChatSession();

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    sendMessage(input, currentMode);
    setInput('');
  };

  return (
    <form onSubmit={handleSubmit} className="p-4 border-t">
      <div className="flex gap-2 items-end">
        {/* 左侧：chat/ask 模式切换 */}
        <Select value={currentMode} onValueChange={(v) => setMode(v)}>
          <SelectTrigger className="w-[90px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="chat">Chat</SelectItem>
            <SelectItem value="ask">Ask</SelectItem>
          </SelectContent>
        </Select>

        {/* 中间：文本输入 */}
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入消息..."
          className="min-h-[60px] resize-none flex-1"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSubmit(e);
            }
          }}
        />

        {/* 右侧：发送/取消按钮 */}
        {isStreaming ? (
          <Button type="button" variant="destructive" onClick={cancelStream}>
            <Square className="w-4 h-4" />
          </Button>
        ) : (
          <Button type="submit" disabled={!input.trim()}>
            <Send className="w-4 h-4" />
          </Button>
        )}
      </div>
    </form>
  );
}
```

### 4.6 useChatSession Hook

封装会话管理和消息发送的完整流程。

```typescript
// lib/hooks/useChatSession.ts

export function useChatSession(notebookId: string) {
  // 暴露方法
  return {
    sendMessage,    // (message, mode, context?) => void
    cancelStream,   // () => void
    switchSession,  // (sessionId) => void
    createSession,  // (title) => Promise<Session>
    deleteSession,  // (sessionId) => void
  };
}
```

sendMessage 的模式路由逻辑：
- mode 为 chat/ask -> 乐观更新主消息列表，SSE 事件更新 messages
- mode 为 explain/conclude -> 更新 chat-store 的 explainCard 字段，SSE 事件更新 explainCard.content

详细接口定义见 `plan-1/02-chat-system/dfd-interface.md`。

---

## 5. Studio 面板

Studio Panel 的具体功能尚未确定。当前保留面板骨架组件：

```typescript
// components/studio/studio-panel.tsx

export function StudioPanel() {
  return (
    <div className="h-full flex items-center justify-center text-muted-foreground">
      <p>Studio（即将推出）</p>
    </div>
  );
}
```

后续确定功能方向后补充具体组件设计。

---

## 6. 组件样式规范

### 6.1 间距

| 场景 | 间距 |
|------|------|
| 面板内边距 | p-4 |
| 卡片内边距 | p-3 |
| 元素间距 | space-y-2 或 gap-2 |
| 段落间距 | mb-4 |

### 6.2 字体

| 场景 | 类名 |
|------|------|
| 面板标题 | text-lg font-semibold |
| 卡片标题 | font-medium |
| 正文 | text-base |
| 辅助文字 | text-sm text-muted-foreground |

### 6.3 颜色

使用 shadcn/ui 的 CSS 变量，自动适应 light/dark 模式：

| 用途 | 变量 |
|------|------|
| 背景 | bg-background |
| 卡片 | bg-card |
| 强调 | bg-muted |
| 主色 | bg-primary |
| 文字 | text-foreground |
| 次要文字 | text-muted-foreground |
