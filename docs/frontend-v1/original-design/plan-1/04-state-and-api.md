# 状态管理与 API 层 -- 设计说明

---

## 1. 设计目标

提供前端的状态管理基础设施和后端 API 的封装层，为各业务模块提供统一的数据获取、缓存和状态管理能力。

---

## 2. 职责

- 定义 Zustand stores 管理客户端状态（UI 状态、面板状态、当前上下文）
- 封装 TanStack Query 管理服务端状态（数据获取、缓存、失效、乐观更新）
- 提供 API 请求函数，统一处理请求构建、错误格式化、类型定义
- 封装 SSE 流解析工具函数，供聊天系统使用

---

## 3. 非职责

- 不定义业务逻辑（各模块的 hooks 负责组合状态和 API 调用）
- 不处理 UI 渲染
- 不管理路由状态（由 Next.js App Router 管理）

---

## 4. Zustand Store 划分

| Store | 存储内容 | 持久化 |
|-------|----------|--------|
| ui-store | 面板折叠状态、当前视图模式、侧边栏状态 | localStorage |
| reader-store | 当前查看的文档 ID、文本选择上下文（document_id + selected_text）、选择菜单位置 | 不持久化 |
| chat-store | 当前会话 ID、消息列表、流式状态标记、当前 mode、explain/conclude 卡片内容 | 不持久化 |

设计原则：
- Zustand 只存储客户端状态，不缓存服务端数据（服务端数据由 TanStack Query 管理）
- 每个 store 职责单一，按 UI 关注点划分
- 需要跨组件共享的临时状态（如流式进行中标记）放 Zustand，组件内部状态用 useState

---

## 5. TanStack Query 策略

### 5.1 Query Key 规范

```
['notebooks']                          -- Notebook 列表
['notebook', notebookId]               -- 单个 Notebook 详情
['notebook-documents', notebookId]     -- Notebook 内文档列表
['library-documents', filters]         -- Library 文档列表（含过滤参数）
['document', documentId]               -- 单个文档元数据
['document-content', documentId]       -- 文档 Markdown 内容
['sessions', notebookId]               -- 会话列表
['messages', sessionId, filters]       -- 消息历史（含 mode 过滤）
```

### 5.2 缓存与失效策略

| 数据 | staleTime | 失效时机 |
|------|-----------|----------|
| Notebook 列表 | 30s | 创建/删除 Notebook 时 |
| 文档列表 | 30s | 上传/删除文档时 |
| 文档内容 | 5min | 文档重新处理完成时 |
| 会话列表 | 10s | 创建/删除会话时 |
| 消息历史 | 不缓存 | 每次进入会话重新加载 |

### 5.3 文档处理状态轮询

当 Notebook 中有文档正在处理时，使用 `refetchInterval` 自动轮询文档列表：

- 轮询间隔：3 秒
- 停止条件：所有文档 status 均为终态（completed 或 failed）
- 轮询目标：GET /notebooks/{id}/documents（批量轮询，不逐个文档轮询）
- 文档从 uploaded → pending → processing → completed 的全过程通过此轮询跟踪

### 5.4 Mutation 模式

所有写操作使用 useMutation，成功后通过 `queryClient.invalidateQueries` 失效相关查询：

- 创建 Notebook → 失效 `['notebooks']`
- 上传文档到 Library → 失效 `['library-documents']`
- 添加文档到 Notebook → 失效 `['notebook-documents', notebookId]`（触发轮询）
- 从 Notebook 移除文档 → 失效 `['notebook-documents', notebookId]`
- 删除 Library 文档 → 失效 `['library-documents']` 和所有 `['notebook-documents']`
- 创建会话 → 失效 `['sessions', notebookId]`
- 删除会话 → 失效 `['sessions', notebookId]`

---

## 6. API 层结构

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

API 函数使用原生 fetch（不引入 axios），保持与 SSE 流的技术一致性。错误统一转换为 `ApiError` 类型，包含 status、error_code、message 字段。

---

## 7. SSE 流解析工具

在 `lib/utils/sse-parser.ts` 中提供通用的 SSE 解析函数：

- 接收 `ReadableStream<Uint8Array>` 作为输入
- 维护文本缓冲区，按 `\n\n` 切分完整事件
- 提取 `data:` 行内容并解析为 JSON
- 通过回调分发不同类型的事件

该工具函数不绑定聊天业务逻辑，可被任何需要 SSE 解析的场景复用。
