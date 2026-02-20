# 前端架构设计

## 1. 概述

本文档描述 Newbee Notebook 前端的整体架构设计，包括页面布局、数据流和状态管理。各模块的详细设计见 `plan-1/` 目录下的对应文档。

---

## 2. 页面布局

### 2.1 三栏布局

```
+------------------------------------------------------------------+
|  Header: NewBee - {Notebook 标题}            [Settings] [Theme]  |
+------------------+------------------------+----------------------+
|                  |                        |                      |
|    Sources       |      Main Panel        |       Studio         |
|    Panel         |                        |       Panel          |
|                  |  [Chat View] 默认      |                      |
|   [+ Add]        |  [Reader View] 查看    |    （待定，后续      |
|                  |    文档时切换          |      补充具体内容）  |
|   文档 1         |                        |                      |
|   [View]         |   AI 回复 ...          |                      |
|                  |                        |                      |
|   文档 2         |   +---------------+    |                      |
|   [View]         |   | 输入框 ...    |    |                      |
|                  |   +---------------+    |                      |
|                  |                        |                      |
+------------------+------------------------+----------------------+
     可折叠              主区域                    可折叠
```

### 2.2 布局组件结构

```
AppShell
├── Header
│   ├── Logo
│   ├── NotebookTitle
│   └── Actions (Settings, Theme)
└── MainContent
    └── ResizablePanelGroup (horizontal)
        ├── ResizablePanel (Sources)
        │   ├── SourceList（默认）
        │   └── DocumentReader（查看文档时）
        ├── ResizableHandle
        ├── ResizablePanel (Main)
        │   ├── ChatPanel（Chat View，默认）
        │   └── MarkdownViewer（Reader View，查看文档时）
        ├── ResizableHandle
        └── ResizablePanel (Studio)
            └── StudioPanel（待定）
```

### 2.3 面板尺寸

| 面板 | 默认宽度 | 最小宽度 | 最大宽度 | 可折叠 |
|------|----------|----------|----------|--------|
| Sources | 25% | 240px | 40% | 是 |
| Main | 50% | 360px | 无限制 | 否 |
| Studio | 25% | 240px | 40% | 是 |

使用 `react-resizable-panels`（Radix UI 生态）实现面板拖拽调整。面板宽度比例和折叠状态持久化到 localStorage。

### 2.4 Main Panel 视图模式

Main Panel 内部支持多种视图，通过 UI 状态管理切换，不影响路由：

- **Chat View**：聊天面板占满 Main Panel（默认）
- **Reader View**：Markdown 查看器占满 Main Panel（从 Sources Panel 点击"查看"文档触发）
- **Split View**（后续迭代）：上下分屏，上方 Markdown 查看器，下方聊天面板

### 2.5 Session 选择器

ChatPanel 顶部包含 Session 选择器，使用 Select/Combobox 下拉组件：
- 默认选中最近会话（GET /notebooks/{id}/sessions/latest）
- 首次进入若无会话，第一条消息发送时自动创建
- 支持切换会话、新建会话、删除会话

### 2.6 Studio Panel

Studio Panel 的具体功能尚未确定，当前作为预留位置。布局层面保留面板骨架（可折叠、可调宽度），内部内容后续补充。

---

## 3. 页面路由

```
/                           # 首页，重定向到 /notebooks
/notebooks                  # Notebook 列表页
/notebooks/[id]             # Notebook 详情页（三栏布局）
/library                    # Library 文档管理页
```

Notebook 详情页是三栏布局的唯一使用场景。列表页和 Library 页使用常规单栏布局。

### 3.1 App Router 结构

```
app/
  layout.tsx                 -- 根布局（ThemeProvider, QueryProvider）
  page.tsx                   -- 首页重定向
  notebooks/
    page.tsx                 -- Notebook 列表
    [id]/
      page.tsx               -- Notebook 详情（三栏布局）
      layout.tsx             -- 详情页布局（含面板状态管理）
  library/
    page.tsx                 -- Library 管理
```

### 3.2 API 代理

```
next.config.ts rewrites:
  /api/v1/:path* -> http://localhost:8000/api/v1/:path*
```

所有 API 请求和图片资源请求通过 Next.js 转发，避免跨域问题。后端资产端点 `GET /api/v1/documents/{document_id}/assets/{asset_path}` 也通过此代理访问。

---

## 4. 状态管理

### 4.1 Store 设计

**ui-store**：面板折叠状态、当前视图模式（Chat View / Reader View）、侧边栏状态。持久化到 localStorage。

**reader-store**：当前查看的文档 ID、文本选择上下文（document_id + selected_text）、选择菜单位置。不持久化。

```typescript
interface ReaderState {
  currentDocumentId: string | null;

  // 文本选中
  selection: { documentId: string; selectedText: string } | null;
  isMenuVisible: boolean;
  menuPosition: { top: number; left: number } | null;

  // Actions
  openDocument: (documentId: string) => void;
  closeDocument: () => void;
  setSelection: (selection: ReaderState['selection']) => void;
  showMenu: (position: { top: number; left: number }) => void;
  hideMenu: () => void;
}
```

**chat-store**：当前会话 ID、消息列表、流式状态标记、当前 mode、explain/conclude 卡片内容。不持久化。

```typescript
interface ChatState {
  // 会话
  currentSessionId: string | null;

  // chat/ask 模式消息
  messages: Message[];
  isStreaming: boolean;
  currentMode: 'chat' | 'ask';
  streamingMessageId: number | null;

  // explain/conclude 模式（独立于主消息列表）
  explainCard: {
    visible: boolean;
    content: string;
    isStreaming: boolean;
    selectedText: string;
    mode: 'explain' | 'conclude';
  } | null;

  // Actions
  addMessage: (message: Message) => void;
  updateMessage: (id: string, updates: Partial<Message>) => void;
  appendContent: (id: string, delta: string) => void;
  setStreaming: (isStreaming: boolean) => void;
  setMode: (mode: 'chat' | 'ask') => void;
  clearMessages: () => void;
  setExplainCard: (card: ChatState['explainCard']) => void;
  appendExplainContent: (delta: string) => void;
}
```

设计原则：
- Zustand 只存储客户端状态，不缓存服务端数据（服务端数据由 TanStack Query 管理）
- 每个 store 职责单一，按 UI 关注点划分
- explain/conclude 的内容独立于主消息列表，使用 `explainCard` 字段管理

### 4.2 数据获取

使用 TanStack Query 管理服务端状态：

```typescript
// Query Key 规范
['notebooks']                          -- Notebook 列表
['notebook', notebookId]               -- 单个 Notebook 详情
['notebook-documents', notebookId]     -- Notebook 内文档列表
['library-documents', filters]         -- Library 文档列表
['document', documentId]               -- 单个文档元数据
['document-content', documentId]       -- 文档 Markdown 内容
['sessions', notebookId]               -- 会话列表
['messages', sessionId, filters]       -- 消息历史
```

写操作使用 `useMutation`，成功后通过 `queryClient.invalidateQueries` 失效相关查询。

---

## 5. 数据流

### 5.1 文档查看流程

```
用户在 Sources Panel 点击 View 按钮
  |
  v
更新 reader-store.currentDocumentId
  |
  v
Main Panel 切换为 Reader View
  |
  v
TanStack Query 加载文档内容（GET /documents/{id}/content?format=markdown）
  |
  v
MarkdownViewer 通过 unified 管线渲染内容
  |
  v
图片路径已由后端在保存时转换为 /api/v1/documents/{id}/assets/images/{hash}.jpg
  |
  v
浏览器通过 Next.js 代理请求图片资源（前端无需做路径转换）
```

### 5.2 文本选中流程

```
用户在 MarkdownViewer 渲染区域中选中文字
  |
  v
useTextSelection hook 检测选中（200ms 防抖）
  |
  v
计算浮动菜单位置（Selection API getBoundingClientRect）
  |
  v
SelectionMenu 显示在选中区域附近
  |
  v
用户点击 Explain 或 Conclude
  |
  v
调用 useChatSession.sendMessage：
  mode: "explain" 或 "conclude"
  context: { document_id, selected_text }
  |
  v
ExplainCard 浮动卡片显示，实时接收流式回复
  |
  v
流结束后 ExplainCard 显示完整内容，用户可关闭卡片
```

explain/conclude 的回复展示在独立的浮动卡片（ExplainCard）中，不混入主聊天面板的消息列表。

### 5.3 聊天流程（chat/ask 模式）

```
用户在 ChatInput 输入消息并发送
  |
  v
会话管理层检查当前会话：
  ├── 无当前会话 -> 自动创建会话（POST /notebooks/{id}/sessions）
  └── 有当前会话 -> 继续
  |
  v
乐观更新：立即向消息列表追加用户消息（role: user）
  |
  v
SSE 流式请求：POST /chat/notebooks/{notebookId}/chat/stream
  |
  v
接收 SSE 事件流：
  ├── start 事件 -> 创建 assistant 消息占位，记录 message_id
  ├── content 事件 -> 将 delta 追加到 assistant 消息内容，UI 实时更新
  ├── sources 事件 -> 将来源数组附加到 assistant 消息
  ├── heartbeat 事件 -> 忽略
  ├── done 事件 -> 标记流结束
  └── error 事件 -> 标记消息为错误状态
  |
  v
流结束后：更新消息列表最终状态
```

### 5.4 流式取消流程

```
用户点击取消按钮
  |
  v
客户端：AbortController.abort() 关闭 SSE 连接
  |
  v
同时：POST /chat/stream/{message_id}/cancel 通知后端停止生成
  |
  v
保留已接收的部分内容，标记消息为已取消状态
```

---

## 6. API 层设计

### 6.1 API 模块

```
lib/api/
  client.ts          -- fetch 封装，统一添加 Content-Type、错误处理
  notebooks.ts       -- Notebook CRUD
  documents.ts       -- 文档上传、元数据、内容获取
  sessions.ts        -- 会话 CRUD
  chat.ts            -- 聊天请求（流式/非流式/取消）
  library.ts         -- Library 文档列表、删除
  types.ts           -- 请求/响应类型定义
```

API 函数使用原生 fetch，不引入 axios。错误统一转换为 `ApiError` 类型，包含 status、error_code、message 字段。

### 6.2 SSE 流解析工具

在 `lib/utils/sse-parser.ts` 中提供通用的 SSE 解析函数，不绑定聊天业务逻辑：

- 接收 `ReadableStream<Uint8Array>` 作为输入
- 维护文本缓冲区，按 `\n\n` 切分完整事件
- 提取 `data:` 行内容并解析为 JSON
- 通过回调分发不同类型的事件

---

## 7. 错误处理

### 7.1 全局错误边界

使用 Next.js App Router 的 `error.tsx` 约定文件处理页面级错误，提供重试按钮。

### 7.2 API 错误处理

```typescript
class ApiError extends Error {
  status: number;
  error_code: string;
  message: string;
}
```

TanStack Query 的 `onError` 回调配合 toast 通知展示用户可见的错误信息。

---

## 8. 性能优化

### 8.1 代码分割

使用 `next/dynamic` 动态导入重量级组件（如 MarkdownViewer），减少首屏 bundle 体积。

### 8.2 长文档渲染

使用 CSS `content-visibility: auto` 属性对 Markdown 渲染区域的子元素做懒渲染，浏览器自动跳过视口外内容的布局和绘制。不引入虚拟滚动方案，后续按需升级。

### 8.3 防抖

文本选中事件使用 200ms 防抖，避免拖拽选择过程中频繁触发菜单显示。

### 8.4 自动滚动

聊天消息列表的自动滚动策略：
- 用户在列表底部（距底部 < 100px）-> 新消息到达时自动滚动
- 用户已向上滚动查看历史 -> 不自动滚动，显示"新消息"提示

---

## 9. 响应式设计

| 断点 | 宽度 | 布局 |
|------|------|------|
| sm | < 640px | 单栏，Tab 切换 |
| md | 640-1024px | 两栏，隐藏 Studio |
| lg | > 1024px | 三栏完整布局 |

小屏和中屏的适配为基础实现，优先保证大屏三栏布局的体验。
