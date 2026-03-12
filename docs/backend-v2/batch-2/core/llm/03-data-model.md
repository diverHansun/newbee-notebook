# LLM 模块：数据模型与 OpenAI SDK 类型参考

## 1. LLMConfig

应用级 LLM 配置。从 llm.yaml 和环境变量加载。

| 字段 | 含义 | 默认值 |
|------|------|--------|
| provider | 当前活跃的 Provider 名称 | "qwen" |
| model | 模型标识 | Provider 默认值 |
| temperature | 生成温度 | 0.7 |
| max_tokens | 最大生成 token 数 | 32768 |
| top_p | 核采样概率 | 0.8 |
| timeout | 单次请求超时（秒） | 60 |
| max_retries | SDK 内置网络层重试次数 | 3 |

## 2. ProviderConfig

单个 Provider 的连接配置。

| 字段 | 含义 |
|------|------|
| name | Provider 名称（"qwen" / "zhipu" / "openai"） |
| api_key | API 密钥 |
| base_url | API 端点 URL |
| model | 默认模型 |
| extra_params | Provider 特定参数（如 Qwen 的 enable_search） |

三个 Provider 的默认配置：

| Provider | base_url | api_key 环境变量 | 默认 model |
|----------|----------|-----------------|-----------|
| qwen | https://dashscope.aliyuncs.com/compatible-mode/v1 | DASHSCOPE_API_KEY | qwen3.5-plus |
| zhipu | https://open.bigmodel.cn/api/paas/v4 | ZHIPU_API_KEY | glm-4.7-flash |
| openai | https://api.openai.com/v1 | OPENAI_API_KEY | gpt-4o-mini |

## 3. OpenAI SDK 类型参考

LLMClient 的输入和输出直接使用 openai SDK 的类型。以下是 AgentLoop 和 LLMClient 交互中涉及的核心类型。

### 3.1 请求侧：消息类型

消息列表的类型为 `List[ChatCompletionMessageParam]`，其中 ChatCompletionMessageParam 是以下类型的联合：

**ChatCompletionSystemMessageParam**

| 字段 | 类型 | 必填 |
|------|------|------|
| role | Literal["system"] | 是 |
| content | Union[str, List[ContentPartText]] | 是 |
| name | str | 否 |

**ChatCompletionUserMessageParam**

| 字段 | 类型 | 必填 |
|------|------|------|
| role | Literal["user"] | 是 |
| content | Union[str, List[ContentPart]] | 是 |
| name | str | 否 |

**ChatCompletionAssistantMessageParam**

| 字段 | 类型 | 必填 |
|------|------|------|
| role | Literal["assistant"] | 是 |
| content | Union[str, None] | 否 |
| tool_calls | List[ToolCallParam] | 否 |
| refusal | Optional[str] | 否 |

其中 ToolCallParam 结构：
```python
{
    "id": str,            # 工具调用 ID，如 "call_abc123"
    "type": "function",
    "function": {
        "name": str,      # 函数名
        "arguments": str  # JSON 字符串
    }
}
```

**ChatCompletionToolMessageParam**

| 字段 | 类型 | 必填 |
|------|------|------|
| role | Literal["tool"] | 是 |
| content | Union[str, List[ContentPartText]] | 是 |
| tool_call_id | str | 是 |

tool_call_id 必须与 assistant 消息中某个 tool_call 的 id 对应。

### 3.2 请求侧：工具定义

工具定义类型为 `ChatCompletionToolParam`：

```python
{
    "type": "function",
    "function": {
        "name": str,                    # 工具名称
        "description": str,             # 工具描述（可选但建议提供）
        "parameters": dict,             # JSON Schema 格式的参数定义
        "strict": Optional[bool]        # 是否启用严格模式
    }
}
```

parameters 字段使用标准 JSON Schema 格式：
```python
{
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "检索查询词"},
        "search_type": {
            "type": "string",
            "enum": ["hybrid", "semantic", "keyword"]
        }
    },
    "required": ["query"]
}
```

### 3.3 请求侧：tool_choice

`ChatCompletionToolChoiceOptionParam` 的取值：

| 值 | 含义 |
|----|------|
| "auto" | LLM 自主决定是否调用工具（默认） |
| "required" | LLM 必须调用至少一个工具 |
| "none" | LLM 不得调用工具 |
| {"type": "function", "function": {"name": "..."}} | 强制调用指定工具 |

### 3.4 请求侧：关键调用参数

`client.chat.completions.create()` 的关键参数：

| 参数 | 类型 | 说明 |
|------|------|------|
| messages | Iterable[ChatCompletionMessageParam] | 必填，消息列表 |
| model | str | 必填，模型标识 |
| tools | Iterable[ChatCompletionToolParam] | 工具定义列表 |
| tool_choice | ChatCompletionToolChoiceOptionParam | 工具选择策略 |
| stream | bool | 是否流式返回 |
| temperature | float | 生成温度（0-2） |
| max_tokens | int | 最大生成 token 数（已废弃，建议用 max_completion_tokens） |
| max_completion_tokens | int | 最大生成 token 数 |
| top_p | float | 核采样概率 |
| stop | Union[str, List[str]] | 停止序列 |
| stream_options | {"include_usage": bool} | 流式选项，include_usage=True 时最后一个 chunk 包含 usage |
| parallel_tool_calls | bool | 是否允许并行工具调用 |

### 3.5 响应侧：非流式

**ChatCompletion**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | 响应 ID |
| object | "chat.completion" | 固定值 |
| created | int | Unix 时间戳 |
| model | str | 实际使用的模型 |
| choices | List[Choice] | 生成结果 |
| usage | CompletionUsage | Token 使用统计 |

**Choice**

| 字段 | 类型 | 说明 |
|------|------|------|
| index | int | 选项索引 |
| message | ChatCompletionMessage | 生成的消息 |
| finish_reason | str | 终止原因 |

**ChatCompletionMessage**

| 字段 | 类型 | 说明 |
|------|------|------|
| role | "assistant" | 固定值 |
| content | Optional[str] | 文本内容（有 tool_calls 时通常为 None） |
| tool_calls | Optional[List[ChatCompletionMessageToolCall]] | 工具调用列表 |
| refusal | Optional[str] | 拒绝消息 |

**ChatCompletionMessageToolCall**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | 工具调用 ID（如 "call_abc123"） |
| type | "function" | 固定值 |
| function | Function | 函数调用信息 |

Function 包含 name（函数名）和 arguments（JSON 字符串，需要调用方解析）。

**finish_reason 取值**

| 值 | 含义 |
|----|------|
| "stop" | 自然终止或命中停止序列 |
| "tool_calls" | 模型调用了工具 |
| "length" | 达到 max_tokens 限制 |
| "content_filter" | 内容过滤 |

AgentLoop 的判断逻辑：finish_reason="tool_calls" 且 message.tool_calls 非空时执行工具调用循环；finish_reason="stop" 时进入流式输出。

**CompletionUsage**

| 字段 | 类型 | 说明 |
|------|------|------|
| prompt_tokens | int | 提示 token 数 |
| completion_tokens | int | 生成 token 数 |
| total_tokens | int | 总 token 数 |

### 3.6 响应侧：流式

**ChatCompletionChunk**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | 同一流中所有 chunk 共享相同 ID |
| object | "chat.completion.chunk" | 固定值 |
| created | int | Unix 时间戳 |
| model | str | 模型 |
| choices | List[ChunkChoice] | chunk 选项 |
| usage | Optional[CompletionUsage] | 仅在最后一个 chunk（stream_options.include_usage=True 时） |

**ChunkChoice**

| 字段 | 类型 | 说明 |
|------|------|------|
| index | int | 选项索引 |
| delta | ChoiceDelta | 增量内容 |
| finish_reason | Optional[str] | 仅最后一个 chunk 有值 |

**ChoiceDelta**

| 字段 | 类型 | 说明 |
|------|------|------|
| role | Optional[str] | 仅第一个 chunk 有值（"assistant"） |
| content | Optional[str] | 增量文本内容 |
| tool_calls | Optional[List[ChoiceDeltaToolCall]] | 增量工具调用数据 |

**ChoiceDeltaToolCall**（流式工具调用累积）

| 字段 | 类型 | 说明 |
|------|------|------|
| index | int | 标识属于哪个工具调用（用于累积） |
| id | Optional[str] | 仅第一个 delta 有值 |
| type | Optional[str] | 仅第一个 delta 有值（"function"） |
| function | Optional[ChoiceDeltaToolCallFunction] | 包含 name（仅首次）和 arguments（增量片段） |

流式工具调用的累积逻辑：按 index 分组，拼接 arguments 字符串片段，直到 finish_reason="tool_calls"。当前 AgentLoop 设计中工具调用阶段使用非流式，不需要处理此累积逻辑。但 LLMClient.chat_stream() 支持返回包含 tool_calls 的 chunk，以备未来扩展。

## 4. 生命周期

### 4.1 LLMClient

应用级单例。应用启动时由 LLMClientFactory 创建，注入到需要 LLM 调用能力的组件中（AgentLoop、Compressor）。内部的 AsyncOpenAI 实例持有 httpx.AsyncClient 连接池，适合长期复用。

### 4.2 配置

应用启动时加载一次。运行时不支持动态切换 Provider（需要重启应用）。如果未来需要多 Provider 并行（如主 Provider + fallback Provider），可以通过持有多个 LLMClient 实例实现。
