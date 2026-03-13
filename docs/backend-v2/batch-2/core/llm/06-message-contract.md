# LLM 模块：消息协议

## 1. 目标

batch-2 之后，内部消息协议统一为 OpenAI-compatible schema。

这份协议同时服务于：

- `llm`
- `context`
- `engine`
- `session`
- API 层的 SSE 聚合

不再允许各模块分别依赖：

- `LlamaIndex ChatMessage`
- 自定义半结构化 message dict
- mode-specific 特例格式

## 2. 基本原则

### 2.1 内部统一，外部兼容

- 内部 runtime 全部使用 OpenAI-compatible messages
- 对外 API 仍兼容现有 `/chat` 与 `/chat/stream`

### 2.2 消息和事件分离

- `messages`：给模型看的上下文
- `events`：给前端和 session 层看的执行过程

不要把 SSE 事件直接写进消息链。

## 3. 内部消息类型

### 3.1 `system`

```json
{
  "role": "system",
  "content": "..."
}
```

### 3.2 `user`

文本版：

```json
{
  "role": "user",
  "content": "..."
}
```

多 part 版：

```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "..."}
  ]
}
```

batch-2 第一版以文本为主，多模态 part 保留为协议兼容，不在本批落地图片功能。

### 3.3 `assistant`

普通回答：

```json
{
  "role": "assistant",
  "content": "..."
}
```

工具调用：

```json
{
  "role": "assistant",
  "content": null,
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "knowledge_base",
        "arguments": "{\"query\":\"...\"}"
      }
    }
  ]
}
```

### 3.4 `tool`

```json
{
  "role": "tool",
  "tool_call_id": "call_abc123",
  "content": "..."
}
```

## 4. 内部类型边界

### 4.1 `context` 负责产出消息链

`context` 模块输出：

- `list[InternalMessage]`

它不再输出 `LlamaIndex ChatMessage`。

### 4.2 `engine` 负责追加 assistant/tool 消息

`engine` 在执行过程中只做两类追加：

- assistant tool-call messages
- tool result messages

### 4.3 `session` 负责持久化业务消息

持久化层可继续存储业务意义上的 user/assistant turn，但 runtime 内部消息协议以 OpenAI-compatible schema 为准。

## 5. tool call 约束

### 5.1 arguments 必须是 JSON 字符串

这与 OpenAI-compatible function calling 保持一致。

### 5.2 tool role 消息必须带 `tool_call_id`

否则无法与 assistant message 中的 tool call 对齐。

### 5.3 Explain / Conclude 的工具约束不体现在消息协议中

工具约束属于 `LoopPolicy + ToolPolicy`，不属于 message schema。

消息协议只描述“怎么表示”，不描述“什么情况下允许表示”。

## 6. 流式输出映射

### 6.1 非流式工具阶段

工具阶段第一版使用非流式 `chat()`。

因此不需要在 batch-2 第一版支持“流式增量 tool_calls 拼接”作为核心路径。

### 6.2 流式最终回答阶段

`chat_stream()` 产出 chunk 后，runtime 将其映射为：

- `ContentEvent(delta)`
- 最终 `DoneEvent`

### 6.3 预留未来能力

如果未来需要流式工具调用，可支持增量 `tool_calls` 累积，但不作为 batch-2 核心能力。

## 7. 为什么不用 `LlamaIndex ChatMessage`

原因不是“LlamaIndex 不可用”，而是它不适合作为 batch-2 runtime 的统一协议：

- tool calling 最终仍要映射回 OpenAI-compatible schema
- 不同模块围绕 `ChatMessage` 再做二次转换，会扩大语义漂移
- 新 `LLMClient` 和 `AgentRuntime` 需要直接面向 OpenAI SDK 类型

因此 batch-2 统一以 OpenAI-compatible schema 作为内部真源。
