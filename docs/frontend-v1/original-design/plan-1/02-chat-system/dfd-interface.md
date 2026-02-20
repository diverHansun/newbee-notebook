# 聊天系统 -- 数据流与接口

前置文档：[goals-duty.md](./goals-duty.md)、[architecture.md](./architecture.md)

---

## 1. 上下文与范围

聊天系统在前端中的位置：

```
[文本选择交互模块]
    |
    | 传入 mode + context（explain/conclude 触发）
    v
[聊天系统]  <--- [状态管理与 API 层] 提供 notebookId
    |
    | SSE 请求/响应
    v
[后端 Chat API]
    |
    | 图片/来源跳转
    v
[Markdown 查看器] / [文档源面板]
```

本模块与以下外部模块存在数据交互：

- **文本选择交互模块**（上游）：触发 explain/conclude 模式的消息发送，携带选中文本上下文
- **状态管理与 API 层**（上游）：提供当前 notebookId
- **后端 Chat API**（外部）：SSE 流式通信和非流式通信的对端
- **Markdown 查看器**（下游）：AI 回复内容的 Markdown 渲染
- **文档源面板**（下游）：来源引用的点击跳转目标

---

## 2. 数据流描述

### 2.1 chat/ask 模式消息发送与接收

```
用户在 ChatInput 输入文本并发送
  |
  v
会话管理层检查当前会话状态：
  ├─ 无当前会话 → 调用 POST /notebooks/{id}/sessions 创建会话
  └─ 有当前会话 → 继续
  |
  v
乐观更新：立即向消息列表追加用户消息（role: user）
  |
  v
构建请求体：
  {
    message: 用户输入文本,
    mode: "chat" 或 "ask",
    session_id: 当前会话 ID
  }
  |
  v
流式通信层发起 SSE 请求：
  POST /chat/notebooks/{notebookId}/chat/stream
  |
  v
接收 SSE 事件流：
  |
  ├─ start 事件 → 创建 assistant 消息占位，记录 message_id
  |
  ├─ content 事件 → 将 delta 追加到 assistant 消息内容
  |                  UI 实时更新显示
  |
  ├─ sources 事件 → 将来源数组附加到 assistant 消息
  |
  ├─ heartbeat 事件 → 忽略，不影响 UI
  |
  ├─ done 事件 → 标记流结束，更新消息状态为完成
  |
  └─ error 事件 → 标记消息为错误状态，显示错误信息
  |
  v
流结束后：更新消息列表最终状态
```

### 2.2 explain/conclude 模式消息发送与接收

```
文本选择交互模块触发：传入 mode + context
  |
  v
会话管理层检查并发状态：
  ├─ 有进行中的 explain/conclude 流 → 取消前一个流
  └─ 有进行中的 chat/ask 流 → 等待其完成
  |
  v
构建请求体：
  {
    message: "请解释以下内容" 或 "请总结以下内容"（可自动生成）,
    mode: "explain" 或 "conclude",
    session_id: 当前会话 ID,
    context: {
      document_id: 来源文档 ID,
      selected_text: 用户选中的文本
    }
  }
  |
  v
流式通信层发起 SSE 请求（同 chat/ask 流程）
  |
  v
接收 SSE 事件流 → 更新 ExplainCard 中的内容
  |
  v
流结束后：ExplainCard 显示完整回复，用户可关闭卡片
```

### 2.3 会话切换流程

```
用户选择另一个会话
  |
  v
如果当前有进行中的流 → 取消流
  |
  v
更新当前会话 ID
  |
  v
清空本地消息列表
  |
  v
调用 GET /sessions/{sessionId}/messages?limit=50 加载消息历史
  |
  v
消息列表填充完毕，滚动到底部
```

### 2.4 流式取消流程

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

## 3. 接口定义

### 3.1 ChatPanel 组件接口（对外）

| 属性 | 输入含义 | 同步/异步 |
|------|----------|-----------|
| notebookId | 当前 Notebook ID | 同步（props） |

ChatPanel 内部通过 hooks 自行管理会话和消息状态。

### 3.2 ExplainCard 组件接口（对外）

| 属性 | 输入含义 | 同步/异步 |
|------|----------|-----------|
| visible | 卡片是否可见 | 同步（props） |
| content | 当前 explain/conclude 回复内容 | 同步（props） |
| isStreaming | 是否正在流式接收 | 同步（props） |
| selectedText | 用户选中的原文（展示在卡片标题区域） | 同步（props） |
| onClose | 关闭卡片的回调 | 同步（callback） |

### 3.3 发送消息接口（Hook 暴露）

useChatSession Hook 暴露的方法：

| 方法 | 输入含义 | 输出含义 | 同步/异步 |
|------|----------|----------|-----------|
| sendMessage | message: string, mode: ModeType, context?: ChatContext | 无直接返回值，通过状态更新反映结果 | 异步 |
| cancelStream | 无 | 无 | 异步 |
| switchSession | sessionId: string | 无 | 异步 |
| createSession | title: string | 新创建的 session 对象 | 异步 |
| deleteSession | sessionId: string | 无 | 异步 |

### 3.4 SSE 流接口（Hook 暴露）

useChatStream Hook 暴露的方法和状态：

| 接口 | 类型 | 说明 |
|------|------|------|
| startStream | (url, body, callbacks) => void | 建立 SSE 连接并开始接收事件 |
| cancelStream | () => void | 关闭当前连接 |
| isStreaming | boolean | 当前是否有活跃的流 |

callbacks 结构：

| 回调 | 参数 | 触发时机 |
|------|------|----------|
| onStart | { message_id: number } | 收到 start 事件 |
| onContent | { delta: string } | 收到 content 事件 |
| onSources | { sources: Source[] } | 收到 sources 事件 |
| onDone | 无 | 收到 done 事件 |
| onError | { error_code: string, message: string } | 收到 error 事件或连接异常 |

### 3.5 后端 API 调用（API 适配层）

| 函数 | HTTP 方法 | 端点 | 请求体 | 返回 |
|------|-----------|------|--------|------|
| chatStream | POST | /chat/notebooks/{id}/chat/stream | ChatRequest | ReadableStream（SSE） |
| chatSync | POST | /chat/notebooks/{id}/chat | ChatRequest | ChatResponse |
| cancelStream | POST | /chat/stream/{messageId}/cancel | 无 | 204 |
| createSession | POST | /notebooks/{id}/sessions | { title } | SessionResponse |
| listSessions | GET | /notebooks/{id}/sessions | 无 | SessionListResponse |
| getLatestSession | GET | /notebooks/{id}/sessions/latest | 无 | SessionResponse |
| deleteSession | DELETE | /sessions/{id} | 无 | 204 |
| getMessages | GET | /sessions/{id}/messages | ?limit&offset&mode | MessageListResponse |

ChatRequest 结构：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| message | string | 是 | 用户消息文本 |
| mode | "chat" / "ask" / "explain" / "conclude" | 是 | 聊天模式 |
| session_id | string (UUID) | 否 | 会话 ID，不传则由后端创建 |
| context | { document_id: string, selected_text: string } | 否 | explain/conclude 模式必填 |

---

## 4. 数据所有权与责任

| 数据 | 创建者 | 消费者 | 本模块的责任 |
|------|--------|--------|-------------|
| 用户消息文本 | 用户（通过 ChatInput） | 聊天系统 → 后端 | 创建并发送到后端 |
| AI 回复内容 | 后端（通过 SSE） | 聊天系统 → MessageItem → MarkdownViewer | 接收、组装并传递给渲染层 |
| 消息列表（本地） | 聊天系统 | UI 组件层 | 创建并维护，与后端保持最终一致 |
| 会话列表 | 后端 | 聊天系统 | 从后端加载并缓存，创建/删除时同步 |
| 来源引用数组 | 后端（通过 SSE sources 事件） | SourcesCard | 接收并附加到对应消息 |
| message_id | 后端（通过 SSE start 事件） | 聊天系统（用于取消流） | 接收并存储，用于流式取消请求 |
| 流式状态标记 | 聊天系统 | UI 组件层（控制按钮状态、加载指示） | 创建并维护 |
| context（选中文本上下文） | 文本选择交互模块 | 聊天系统 | 只读消费，拼接到请求体中 |
| notebookId | 路由参数 / 状态管理层 | 聊天系统 | 只读消费，用于构建 API 路径 |
