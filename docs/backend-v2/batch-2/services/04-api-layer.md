# API 层适配设计

## 1. 当前 API 层结构

### 1.1 Chat 相关端点

`api/routers/chat.py` 提供两个主要端点:

| 端点 | 方法 | 说明 |
|------|------|------|
| `/notebooks/{notebook_id}/chat` | POST | 非流式对话，返回完整 JSON |
| `/notebooks/{notebook_id}/chat/stream` | POST | 流式对话，返回 SSE 事件流 |
| `/stream/{message_id}/cancel` | POST | 取消流式请求（占位，未实现） |

### 1.2 SSE 事件协议

当前 `SSEEvent` 类定义了 6 种事件类型:

| 事件类型 | 方法 | 用途 |
|---------|------|------|
| start | `SSEEvent.start(message_id)` | 标记流开始 |
| thinking | `SSEEvent.thinking(stage)` | 检索/生成阶段提示 |
| content | `SSEEvent.content(delta)` | 文本增量 |
| sources | `SSEEvent.sources(sources, sources_type)` | 引用来源 |
| done | `SSEEvent.done()` | 标记流结束 |
| error | `SSEEvent.error(code, message)` | 错误 |
| heartbeat | `SSEEvent.heartbeat()` | 心跳保活 |

事件通过 `sse_adapter` 从 ChatService 产出的 dict 事件转换为 SSE 格式字符串:

```python
async def sse_adapter(stream: AsyncGenerator[dict, None]) -> AsyncGenerator[str, None]:
    async for event in stream:
        event_type = event.get("type")
        payload = {k: v for k, v in event.items() if k != "type"}
        yield SSEEvent.format(event_type, payload)
```

`heartbeat_generator` 包装 `sse_adapter`，在空闲时发送心跳事件，防止代理/负载均衡器关闭空闲连接。

### 1.3 请求模型

`ChatRequest`（定义在 `chat.py` 内）:

```python
class ChatRequest(BaseModel):
    message: str
    mode: Literal["chat", "ask", "explain", "conclude"]
    session_id: Optional[str]
    context: Optional[ChatContext]
    include_ec_context: Optional[bool]
    source_document_ids: Optional[list[str]]
```

`ChatContext`（`api/models/requests.py`）:

```python
class ChatContext(BaseModel):
    selected_text: Optional[str]
    chunk_id: Optional[str]
    document_id: Optional[str]
    page_number: Optional[int]
```

### 1.4 响应模型

`ChatResponse`（定义在 `chat.py` 内，非流式接口）:

```python
class ChatResponse(BaseModel):
    session_id: str
    message_id: int
    content: str
    mode: str
    sources: list
```

### 1.5 异常处理

分两层:

流式端点 -- `prevalidate_mode_requirements()` 在 SSE 连接建立前调用:
- `ValueError` -> HTTP 400
- `RuntimeError` -> HTTP 503
- `DocumentProcessingError` -> 被全局异常处理器捕获，返回 HTTP 409 JSON

非流式端点 -- `chat()` 调用中:
- `ValueError` -> HTTP 400
- `RuntimeError` -> HTTP 503
- OpenAI SDK 异常 -> 转发其 status_code
- `DocumentProcessingError` -> 被全局异常处理器捕获，返回 HTTP 409 JSON

全局异常处理器（`api/middleware/error_handler.py`）:

```python
async def newbee_notebook_exception_handler(request, exc: NewbeeNotebookException):
    return JSONResponse(status_code=exc.http_status, content=exc.to_dict())
```

输出格式:

```json
{
    "error_code": "E4001",
    "message": "文档正在处理中，请稍后重试",
    "details": { ... }
}
```

## 2. 阻塞修复需要的 API 层变更

### 2.1 SSEEvent 新增 warning 方法

```python
@staticmethod
def warning(code: str, message: str, details: Optional[dict] = None) -> str:
    payload = {"code": code, "message": message}
    if details:
        payload["details"] = details
    return SSEEvent.format("warning", payload)
```

`sse_adapter` 无需修改 -- 它是通用的 dict-to-SSE 转换，ChatService 产出 `{"type": "warning", ...}` 会自动被序列化。新增 `SSEEvent.warning()` 仅为代码可读性和一致性。

### 2.2 ChatResponse 新增 warnings 字段

非流式接口需要传递 warning 信息:

```python
class ChatResponse(BaseModel):
    session_id: str
    message_id: int
    content: str
    mode: str
    sources: list = Field(default_factory=list)
    warnings: list = Field(default_factory=list)
```

`warnings` 默认为空列表，向后兼容。非流式端点的返回逻辑调整:

```python
return ChatResponse(
    session_id=result.session_id,
    message_id=result.message_id,
    content=result.content,
    mode=result.mode.value,
    sources=[s.__dict__ for s in result.sources],
    warnings=result.warnings,
)
```

### 2.3 SSE 事件时序变更

当前:

```
start -> thinking -> content... -> sources -> done
```

阻塞修复后:

```
start -> warning(如有) -> thinking -> content... -> sources -> done
```

warning 事件位于 start 之后、thinking 之前。前端可选择处理或忽略。

## 3. Core 重构需要的 API 层变更

### 3.1 新增 SSE 事件类型

AgentLoop 的 StreamEvent 引入新的事件类型，需要在 SSEEvent 中增加对应方法:

| 新事件 | 方法 | 用途 |
|--------|------|------|
| phase | `SSEEvent.phase(phase)` | 替代 thinking，更精确的阶段标记 |
| tool_call | `SSEEvent.tool_call(name, arguments)` | 工具调用开始 |
| tool_result | `SSEEvent.tool_result(name, success)` | 工具调用结果 |

注意: `sse_adapter` 的通用转换逻辑使得即使不新增方法，新事件类型也能正常序列化。新增方法是为了代码一致性和类型安全。

### 3.2 thinking 事件向后兼容

当前前端依赖 `thinking` 事件类型。重构后 AgentLoop 产出 `PhaseEvent`，ChatService 可以选择:

方案 A -- 保持 thinking 不变:

```python
if isinstance(event, PhaseEvent):
    yield {"type": "thinking", "stage": event.phase}
```

方案 B -- 新增 phase，逐步弃用 thinking:

```python
if isinstance(event, PhaseEvent):
    yield {"type": "phase", "phase": event.phase}
```

建议方案 A，减少前端适配工作。

### 3.3 ChatRequest 变更

`include_ec_context` 字段在 core 重构后不再需要（双轨上下文由 context 模块自动管理）。处理方式:

- 保留字段但标记废弃，避免前端立即报错
- 后端忽略此字段的值
- 下一版本移除

`source_document_ids` 字段保留不变，继续用于 Agent/Ask 模式的检索范围选择。

### 3.4 ChatContext 无变更

`ChatContext` 的 4 个字段（selected_text, chunk_id, document_id, page_number）在重构后仍然需要:
- `selected_text` + `document_id`: Explain/Conclude 模式的用户选区
- `chunk_id` + `document_id`: `_get_context_chunks()` 的邻近 chunk 检索
- `page_number`: 保留，前端使用

## 4. 全局异常处理无变更

`error_handler.py` 中的 `newbee_notebook_exception_handler` 已正确处理所有 `NewbeeNotebookException` 子类（包括 `DocumentProcessingError`），无需修改。

阻塞修复后 `DocumentProcessingError` 的 message 和 details 内容变化，但异常处理器是通用的，不关心具体内容。

## 5. 变更汇总

### 阻塞修复（独立，可先行）

| 文件 | 变更 |
|------|------|
| `api/routers/chat.py` | `SSEEvent.warning()` 新增、`ChatResponse.warnings` 字段 |
| `api/middleware/error_handler.py` | 无变更 |
| `api/models/requests.py` | 无变更 |
| `api/models/responses.py` | 无变更（ChatResponse 定义在 chat.py 内） |

### Core 重构适配

| 文件 | 变更 |
|------|------|
| `api/routers/chat.py` | `SSEEvent` 新增 phase/tool_call/tool_result 方法、`include_ec_context` 标记废弃 |
| `api/dependencies.py` | SessionManager 构造参数调整、ChatService 注入 pgvector_index、import 路径变更 |
| `api/middleware/error_handler.py` | 无变更 |
| `api/models/requests.py` | 无变更 |
| `api/models/responses.py` | 无变更 |
