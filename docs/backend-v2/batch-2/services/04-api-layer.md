# API 层适配设计

## 1. 总体原则

batch-2 的 API 层遵循两条原则：

1. **外部接口先兼容**
2. **内部 runtime 完全换新**

也就是说：

- 路由路径先不大改
- 旧 `mode=chat` 先保留 alias
- 但内部已经全部映射到新的 runtime、message contract 和 StreamEvent

## 2. 路由兼容策略

保持现有端点：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/notebooks/{notebook_id}/chat` | POST | 非流式对话 |
| `/notebooks/{notebook_id}/chat/stream` | POST | 流式对话 |
| `/stream/{message_id}/cancel` | POST | 取消流式请求 |

### 2.1 mode 兼容

- 对外仍允许：`chat`, `agent`, `ask`, `explain`, `conclude`
- 对内统一：
  - `chat -> agent`

这样前端可以逐步迁移，不需要 batch-2 中途一起硬切。

## 3. 请求模型

建议请求模型：

```python
class ChatRequest(BaseModel):
    message: Optional[str]
    mode: Literal["chat", "agent", "ask", "explain", "conclude"]
    session_id: Optional[str]
    context: Optional[ChatContext]
    source_document_ids: Optional[list[str]]
    rag_config: Optional[dict]
    include_ec_context: Optional[bool]
```

### 3.1 字段语义

- `message`
  - `agent / ask` 必填
  - `explain / conclude` 可选
- `context.selected_text`
  - `explain / conclude` 必填
- `context.document_id`
  - `explain / conclude` 必填
- `include_ec_context`
  - 保留兼容
  - batch-2 内部忽略

## 4. SSE 正式协议

batch-2 正式事件类型：

- `start`
- `warning`
- `phase`
- `tool_call`
- `tool_result`
- `sources`
- `content`
- `done`
- `error`
- `heartbeat`

### 4.1 `phase`

正式阶段值：

- `reasoning`
- `retrieving`
- `synthesizing`

### 4.2 `thinking` 的处理

`thinking` 不是 batch-2 的正式协议，只是兼容旧前端的临时映射。

建议 API adapter：

- 新前端读 `phase`
- 旧前端如仍依赖 `thinking`，由 adapter 做映射

## 5. 非流式接口

非流式接口不再维护独立执行路径。

建议统一做法：

- 复用流式 runtime
- 在 API/service 层聚合：
  - `content`
  - `sources`
  - `warnings`

这能避免双执行链继续分裂。

## 6. Source 协议

前端统一消费一套 source 数据：

```json
{
  "document_id": "...",
  "chunk_id": "...",
  "title": "...",
  "text": "...",
  "score": 0.0,
  "source_type": "retrieval"
}
```

不再区分 chat / ask / explain 的不同外观结构。

## 7. Explain / Conclude 的输入规则

Explain / Conclude 来自文档阅读器中的选区，因此 API 层必须明确校验：

- `context.selected_text` 必填
- `context.document_id` 必填
- `message` 可选

这类请求进入新的 retrieval-required loop，不再走 QueryEngine。

## 8. warning 事件

warning 是 batch-2 继续保留的正式事件，用于传递非阻断提示，例如：

- 部分文档仍在处理中
- scope 被 runtime 收窄
- 检索结果质量一般，系统继续补检

## 9. 错误输出

流式错误建议结构：

```json
{
  "code": "runtime_error",
  "message": "...",
  "retriable": false
}
```

非流式错误仍走全局异常处理器和标准 JSONResponse。
