# 聊天系统 -- 架构设计

前置文档：[goals-duty.md](./goals-duty.md)

---

## 1. 架构概览

聊天系统由四个子组件构成，按职责垂直分层：

```
用户交互
    |
    v
[UI 组件层]  ChatPanel / ExplainCard / MessageItem / ChatInput
    |
    v
[会话管理层]  会话列表、会话切换、消息列表维护
    |
    v
[流式通信层]  SSE 连接管理、事件解析、增量内容组装
    |
    v
[API 适配层]  请求构建、端点调用、响应类型定义
```

- **UI 组件层**：负责消息列表的渲染、用户输入的收集、模式切换的交互。chat/ask 模式使用主面板组件（ChatPanel），explain/conclude 模式使用浮动卡片组件（ExplainCard）。
- **会话管理层**：维护当前 Notebook 的会话列表和当前活跃会话，管理消息列表的状态（加载、追加、清空）。这一层是聊天系统状态的核心，其他层通过它读写消息数据。
- **流式通信层**：封装 SSE 连接的建立、事件解析、内容增量组装和连接关闭。向上层提供回调接口（onStart、onContent、onSources、onDone、onError）。
- **API 适配层**：构建各种模式的请求参数，调用后端端点（流式/非流式/取消），定义请求和响应的类型。

---

## 2. 设计模式与理由

### 2.1 事件回调模式（流式通信层）

流式通信层不直接操作 UI 状态，而是通过回调函数将事件传递给会话管理层。

选择理由：
- SSE 事件的处理逻辑（解析 JSON、区分事件类型、处理心跳）与 UI 状态更新逻辑（追加消息内容、设置来源引用、更新流式状态标记）属于不同关注点
- 回调模式允许会话管理层决定如何响应每个事件，而不是由通信层直接修改状态

放弃的替代方案：
- **Observable/RxJS 模式**：引入额外依赖，对于单一 SSE 流的场景过于复杂
- **直接在通信层修改 Zustand store**：导致通信层与状态管理耦合，测试困难

### 2.2 乐观更新（消息发送）

用户发送消息后，立即在本地消息列表追加用户消息并显示 AI 消息占位，不等待后端确认。

选择理由：
- 聊天场景对即时反馈敏感，等待后端响应后再显示用户消息会有明显延迟
- 发送失败时，可以标记消息为失败状态供用户重试

代价：
- 需要处理发送失败时的回滚逻辑（标记失败，而非删除已显示的消息）
- 本地 message_id 与后端 message_id 需要在 `start` 事件后同步

### 2.3 模式路由（UI 层）

根据消息的 mode 字段将消息路由到不同的 UI 容器：

- `chat` / `ask` → 主聊天面板（ChatPanel）
- `explain` / `conclude` → 浮动卡片（ExplainCard）

选择理由：
- explain/conclude 是上下文相关的临时交互（针对选中文本的快速解释或总结），与持续性的聊天对话在交互性质上不同
- 浮动卡片不占用主面板空间，用户可以同时查看文档和解释内容
- 后端 API 的消息按 mode 过滤能力支持这种分离展示

放弃的替代方案：
- **所有模式混合在主面板**：explain/conclude 是临时性的、与选中文本强关联的操作，混合展示会打断聊天上下文的连贯性

---

## 3. 模块结构与文件布局

```
components/chat/
  ChatPanel.tsx               -- 主聊天面板（chat/ask 模式）
  ChatInput.tsx               -- 消息输入框
  MessageItem.tsx             -- 单条消息渲染（头像、内容、来源引用）
  SourcesCard.tsx             -- 来源引用卡片
  ExplainCard.tsx             -- explain/conclude 模式的浮动卡片

lib/hooks/
  useChatStream.ts            -- SSE 流式通信 hook
  useChatSession.ts           -- 会话管理 hook（会话列表、切换、消息）

lib/api/
  chat.ts                     -- 聊天相关 API 函数

stores/
  chat-store.ts               -- 聊天状态（消息列表、流式状态、当前会话）
```

各文件职责：

- **ChatPanel.tsx**：主聊天面板的容器组件。顶部包含 Session 选择器（Select/Combobox 下拉，支持切换和新建会话），主体为消息列表，底部为输入框。负责 chat/ask 模式消息的展示和自动滚动。
- **ChatInput.tsx**：消息输入组件。左侧为 chat/ask 模式切换下拉，中间为文本输入区（Enter 发送、Shift+Enter 换行），右侧为发送/取消按钮。流式响应进行中时发送按钮替换为取消按钮。
- **MessageItem.tsx**：单条消息的渲染。区分用户消息和 AI 消息的样式，AI 消息内容通过 MarkdownViewer 渲染，流式进行中显示打字光标效果。
- **SourcesCard.tsx**：AI 消息附带的来源引用展示。列出引用的文档标题，支持点击跳转（跳转逻辑由外部处理）。
- **ExplainCard.tsx**：explain/conclude 模式的浮动卡片。可拖动、可调整大小、可折叠。内部包含消息内容渲染和关闭按钮。
- **useChatStream.ts**：封装 SSE 连接的 React Hook。管理 fetch 请求、ReadableStream 解析、事件分发、连接关闭。提供 `startStream`、`cancelStream` 方法和 `isStreaming` 状态。
- **useChatSession.ts**：封装会话管理逻辑。加载会话列表、切换会话、加载消息历史、处理发送消息的完整流程（乐观更新 → 建立流 → 接收事件 → 更新消息）。
- **chat.ts**：API 函数定义。包括非流式聊天、流式聊天、取消流式、会话 CRUD、消息历史查询。
- **chat-store.ts**：Zustand store。存储当前会话 ID、消息列表、流式状态标记、当前 mode。

### 3.1 外部接口与内部实现的边界

外部模块通过以下方式与聊天系统交互：

- **文本选择交互模块** → 调用 useChatSession 提供的发送方法，传入 mode（explain/conclude）和 context（document_id + selected_text）
- **布局系统** → 将 ChatPanel 放置在中间面板区域，将 ExplainCard 渲染为浮动定位元素
- **Markdown 查看器** → MessageItem 内部使用 MarkdownViewer 渲染 AI 回复内容

---

## 4. 架构约束与权衡

### 4.1 SSE 解析方案

使用原生 `fetch` + `ReadableStream` 解析 SSE，而非 EventSource API 或第三方库。

理由：
- `EventSource` 只支持 GET 请求，而后端的流式端点是 POST 请求
- 原生 fetch 可以设置请求头（Content-Type、Accept）和请求体
- 不引入额外依赖

代价：
- 需要手动解析 SSE 文本格式（`data: {...}\n\n`），包括处理跨 chunk 的行分割
- 需要手动管理连接关闭（AbortController）

SSE 解析的核心逻辑：维护一个文本缓冲区，每次从 ReadableStream 读取到数据时追加到缓冲区，按 `\n\n` 分割完整事件，每个事件提取 `data:` 行并解析为 JSON。

### 4.2 explain/conclude 卡片的状态管理

explain/conclude 的消息不存储在主聊天消息列表中，而是使用独立的状态字段。

理由：
- explain/conclude 是临时交互，关闭卡片后可以丢弃，不需要和 chat/ask 消息混合持久化
- 后端按 mode 分别存储，前端也分别管理，保持一致

权衡：
- 如果后续需要查看 explain/conclude 的历史记录，需要从后端重新加载（通过 `messages?mode=explain,conclude` 端点）

### 4.3 并发流的处理

同一时刻只允许一个活跃的 SSE 流连接。

理由：
- chat/ask 模式一次只能有一个进行中的对话
- explain/conclude 如果在 chat 流进行中触发，需要排队或拒绝

当前策略：如果 chat/ask 流正在进行中，explain/conclude 请求等待当前流结束后再发起。如果 explain/conclude 流正在进行中，新的 explain/conclude 请求取消前一个流并启动新流。

### 4.4 消息历史加载策略

进入会话时加载最近 N 条消息（通过 limit 参数），向上滚动时按需加载更早的消息。

权衡：
- 首次加载的消息数量（N）需要平衡加载速度和用户体验。建议 N=50，覆盖大部分对话场景
- 向上滚动加载使用 TanStack Query 的分页能力，避免重复请求

### 4.5 自动滚动行为

新消息到达时的滚动策略：

- 如果用户当前在消息列表底部（距底部 < 100px）→ 自动滚动到新消息
- 如果用户已向上滚动查看历史消息 → 不自动滚动，显示"新消息"提示

理由：自动滚动到底部是聊天应用的标准行为，但打断用户阅读历史消息的自动滚动是糟糕的体验。
