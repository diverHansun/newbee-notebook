# P5: SSE 流式响应提前取消与非流式降级方案

---

## 1. 当前问题

### 1.1 现象

在所有四种对话模式（chat / ask / explain / conclude）下，后端日志均出现：

```
INFO: Stream cancelled before completion for session {session_id}
```

**用户侧表现**：前端始终无法收到任何响应内容，等待约 30 秒后连接断开。

### 1.2 根本原因：Next.js rewrite 代理缓冲 SSE 响应体

这与文件上传路由的 10MB 限制问题属于同一类架构问题。

`next.config.ts` 中的 rewrite 规则：

```typescript
{ source: "/api/v1/:path*", destination: `${apiHost}/api/v1/:path*` }
```

Next.js 的 `rewrites()` 机制在 Node.js 层面通过 HTTP 代理转发请求。对于普通 JSON 响应，这没有问题。但对于 SSE（Server-Sent Events）流式响应，Next.js 代理会**缓冲整个响应体**，直至后端关闭连接，再一次性转发给浏览器。

结果：
- 后端逐 token 产生 SSE 事件，但全部被代理缓冲
- 前端浏览器端始终收不到任何 data 事件
- 约 30 秒后 Next.js 代理触发默认 HTTP 超时，关闭连接
- 后端 ASGI 服务感知到客户端断开，将 asyncio 任务取消
- `asyncio.CancelledError` 在数据库写入阶段（此时 LLM 已完成）被抛出
- 后端日志：`Stream cancelled before completion for session ...`

**时序验证（来自实际日志）**：
```
23:07:04 - 请求到达，ES 检索完成
23:07:10 - LLM (bigmodel.cn) 开始流式返回 HTTP 200
23:07:34 - Stream cancelled（距请求恰好 30 秒，符合代理默认超时）
```

### 1.2 后端取消日志的位置

**文件**：`newbee_notebook/application/services/chat_service.py`，第 311-313 行

```python
except asyncio.CancelledError:
    logger.info(f"Stream cancelled for session {session_id}")
    return
```

`asyncio.CancelledError` 是 Python 异步框架对协程取消操作的标准信号。触发此路径的前提是：**HTTP 连接在服务端主动写入完 "done" 事件之前就已关闭**。

### 1.3 后端流式响应生命周期

`chat_service.py` 中 `chat_stream()` 方法（第 195-322 行）的完整生命周期如下：

```
POST /chat/notebooks/{id}/chat/stream 请求到达
  -> chat_service.chat_stream() 被调用（异步生成器）
      -> start_session(session_id)       # 第 233 行：初始化 session manager 上下文
      -> yield {"type": "start", ...}   # 第 247 行
      -> while True: await stream.__anext__()  # 第 261-266 行：逐 token 写出
          [每个 token 设有 60 秒超时，第 263 行]
      -> yield {"type": "sources", ...} # 第 273 行
      -> yield {"type": "done"}         # 第 274 行
      -> 持久化消息到数据库            # 第 277-307 行
  Connection closed by client
  -> asyncio.CancelledError raised inside chat_stream()
  -> logger.info("Stream cancelled ...")  # 第 312 行
```

关键问题：**持久化消息（第 277-307 行）在 "done" 事件之后执行**。若客户端在收到 "done" 后立即关闭连接（HTTP 连接关闭快于服务端完成后续异步写入），`asyncio.CancelledError` 会在数据库写入过程中打断执行，导致消息丢失（虽然响应已传递给用户，但历史记录未保存）。

### 1.4 前端连接关闭的触发路径

前端通过 `AbortController` 管理 SSE 连接，位于 `useChatStream.ts`（第 14-79 行）。

**路径一：正常完成（最常见）**

```
stream "done" event 到达
  -> useChatSession.ts 第 271-276 行：updateMessage({ status: "done" }), activeAssistantIdRef = null
  -> chatStream() 的 parseSseStream 循环结束（ReadableStream 关闭）
  -> fetch 连接关闭
  -> 后端 CancelledError 被触发（连接关闭触发，非 abort()）
```

这是最频繁触发 "Stream cancelled" 的路径。SSE 协议中，服务端写完数据后流关闭，客户端 fetch 的 ReadableStream 随之结束。当 ReadableStream 关闭时，底层 HTTP 连接关闭，后端 asyncio 任务接收到取消信号。

这意味着：**在正常流程中，后端 "Stream cancelled" 日志是预期行为，不代表异常**。

**路径二：用户切换会话 / 发送新消息**

```
stream.startStream() 被再次调用（发新消息或切换会话）
  -> useChatStream.ts 第 21-23 行：if (abortRef.current) abortRef.current.abort()
  -> 旧 AbortController 被 abort()
  -> fetch 连接关闭
  -> 后端 CancelledError：旧流被打断，消息不完整且未持久化
```

**路径三：组件卸载（页面跳转、刷新）**

```
组件 cleanup 函数执行（React useEffect return）
  -> useChatStream.ts finally 块运行
  -> abortRef.current?.abort() -> 后端 CancelledError
```

**路径四：40 秒 / 网络超时**

```
网络中断或后端 token 生成超过 60 秒
  -> 后端 asyncio.TimeoutError（第 309-310 行）→ 返回 error event，不走 CancelledError
  -> 或：前端 fetch 超时 -> 连接关闭 -> 后端 CancelledError
```

### 1.5 关键架构缺陷：消息持久化在流结束后

`chat_service.py` 第 277-307 行的消息持久化代码位于 `yield {"type": "done"}` 之后，在同一个 `try` 块内：

```python
yield {"type": "done"}

# 以下代码在 yield 之后执行，若连接已关闭，asyncio.CancelledError 可能在这里发生
await self._message_repo.create_batch([user_msg, assistant_msg])
await self._session_repo.increment_message_count(session_id, 2)
```

这是一个**竞争条件**：客户端收到 "done" 后关闭连接的速度快于服务端完成数据库写入，会导致：
- 用户看到了完整的 AI 回复（"done" 已收到）
- 但刷新页面后历史消息消失（消息未入库）

---

## 2. 解决方案

### 2.1 后端：将消息持久化移到 "done" yield 之前

这是最高优先级修复。

**修改位置**：`chat_service.py` 第 274-290 行

```python
# 修改前：done 之后才持久化
yield {"type": "done"}
await self._message_repo.create_batch([user_msg, assistant_msg])
await self._session_repo.increment_message_count(session_id, 2)

# 修改后：先持久化，再 yield done
await self._message_repo.create_batch([user_msg, assistant_msg])
await self._session_repo.increment_message_count(session_id, 2)
yield {"type": "done"}
```

这样即使客户端在 "done" 到达后立即关闭连接，消息已经写库，`CancelledError` 只会在 TCP 关闭通知阶段被触发，不会影响数据完整性。

### 2.2 前端：SSE 失败自动降级为非流式接口

当 SSE 流被取消（非用户主动取消）时，自动使用 `POST /chat/notebooks/{id}/chat` 接口获取完整响应。

**降级触发条件**：
- `onError` 回调被调用（非用户主动 abort）
- 错误类型为网络错误或连接中断（非业务逻辑错误如 E3001）

**降级实现位置**：`useChatSession.ts`，在 `onError` 回调中写降级逻辑

```typescript
// useChatSession.ts sendMessage() 中，chat/ask 模式的 onError 回调
onError: (error) => {
  const isUserAborted = (error as ApiError)?.errorCode === "AbortError";
  if (isUserAborted) {
    // 用户主动取消，不降级，直接标记错误
    updateMessage(..., { status: "error", content: "已取消" });
    return;
  }
  // 非用户取消，降级为非流式请求
  chatOnce(notebookId, { message, mode, session_id: sessionId, context: context || null })
    .then((result) => {
      updateMessage(assistantLocalId, { content: result.content, status: "done" });
    })
    .catch((fallbackError) => {
      updateMessage(assistantLocalId, { status: "error", content: fallbackError.message });
    });
},
```

### 2.3 前端：发新消息前等待旧流自然结束

在 `useChatStream.ts` `startStream()` 中，当前 `abortRef.current` 非空时直接 abort（第 21-23 行）。可以改为：如果 `isStreaming` 为 true，先等待当前流结束再发出新请求，而不是立即中止。

但这会影响用户体验（需要等待）。更合理的做法是：在 UI 层禁用发送按钮（当 `isStreaming` 为 true 时），强制用户先取消再发送，而不是隐式中止旧流。

---

## 3. 架构影响与修改点

### 后端修改

**`newbee_notebook/application/services/chat_service.py`**

| 变更 | 位置 | 说明 |
|------|------|------|
| 消息持久化移到 yield done 前 | 第 274-307 行重排序 | 消除竞争条件，确保消息入库 |

### 前端修改

**`frontend/src/lib/hooks/useChatSession.ts`**

| 变更 | 位置 | 说明 |
|------|------|------|
| onError 回调增加降级逻辑 | sendMessage 中 chat/ask 流的 onError | 调用 chatOnce 重试 |
| onError 回调增加降级逻辑 | sendMessage 中 explain/conclude 流的 onError | 同上 |

**`frontend/src/lib/api/chat.ts`**（无需修改）

`chatOnce` 已经正确实现并使用 `apiFetch`，可直接用作降级调用。

### 验收标准

- 用户正常对话时，刷新页面后消息历史仍存在
- SSE 连接中断时，前端自动使用非流式接口获取完整回复，不显示流式动画
- 用户主动点击取消时，不触发降级，直接清除消息或标记取消
- 后端 "Stream cancelled" 日志减少（仅在 done 之后的 TCP 关闭环节触发，为正常现象）
