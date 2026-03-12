# Engine 模块：核心概念与数据模型

## 1. AgentLoopConfig

AgentLoopConfig 描述一次 AgentLoop 执行的行为参数。

| 字段 | 含义 | 默认值 |
|------|------|--------|
| max_iterations | 安全熔断：最大工具调用循环次数 | 50 |
| tool_choice | 工具选择策略 | "auto" |
| parallel_tool_calls | 是否允许并行工具调用 | False |
| llm_retry_max | LLM API 错误重试次数 | 3 |
| llm_retry_base_delay | LLM 重试基础延迟（秒） | 1.0 |
| json_fix_max_attempts | tool_calls JSON 解析失败的修正尝试次数 | 2 |

### 1.1 关于 max_iterations

max_iterations 是安全熔断器，不是功能性限制。正常交互中，AgentLoop 通过语义终止退出循环（LLM 返回不含 tool_calls 的响应）。max_iterations 仅在 LLM 异常行为（如死循环调用工具）时触发，产出 ErrorEvent(code="max_iterations") 并终止。

默认值 50 对所有模式统一。这个值足够覆盖最复杂的 Agent 模式任务，同时作为安全上限防止资源耗尽。

### 1.2 关于超时

Engine 模块不设置 total_timeout 和 iteration_timeout。超时控制由以下两层负责：

- **LLM 调用层**：LLMClient 的 AsyncOpenAI 配置 request timeout（默认 60s），控制单次 LLM API 调用的超时。
- **HTTP 层**：API Router 的请求超时和 SSE 连接超时，控制整体请求生命周期。

AgentLoop 作为纯计算组件，不需要感知时间。它的职责是正确地执行循环直到语义终止或安全熔断。

tool_choice 取值：
- `"auto"`：LLM 自主决定是否调用工具。
- `"required"`：LLM 必须调用至少一个工具。用于 Explain/Conclude 首轮。
- `"none"`：LLM 不得调用工具。当前未使用，保留扩展。

## 2. ModeConfig

ModeConfigFactory.build() 的返回值。包含 AgentLoop 初始化和执行所需的全部参数。

| 字段 | 含义 |
|------|------|
| system_prompt | 模式对应的系统提示词 |
| tools | 可用工具列表 |
| agent_loop_config | AgentLoopConfig 实例 |
| user_message | 构造后的用户消息（Explain/Conclude 为基于 selected_text 的构造消息） |

ModeConfig 是一个不可变的数据对象。每次请求生成一个新的 ModeConfig。

## 3. RAGConfig

前端每次请求可传入的 RAG 检索参数。ModeConfigFactory 在构建工具列表时将这些参数注入到 knowledge_base 工具中。

| 字段 | 含义 | 默认值 |
|------|------|--------|
| top_k | 检索返回的文档片段数量 | 5 |
| similarity_threshold | 语义相似度过滤阈值 | 0.3 |
| rerank_enabled | 是否启用重排序 | True |
| rerank_top_n | 重排序后保留的结果数 | 3 |

RAGConfig 属于请求级别的配置，不属于 AgentLoop 的行为配置。AgentLoop 不感知 RAGConfig——它只看到构建好的工具列表。

## 4. 消息格式

AgentLoop 使用 OpenAI 兼容的消息格式。消息链由 context 模块构建，AgentLoop 在循环过程中追加新消息。

### 4.1 消息角色

| 角色 | 用途 | 对应 openai SDK 类型 |
|------|------|---------------------|
| system | 系统提示词 | ChatCompletionSystemMessageParam |
| user | 用户输入 | ChatCompletionUserMessageParam |
| assistant | LLM 回复（含 tool_calls） | ChatCompletionAssistantMessageParam |
| tool | 工具执行结果 | ChatCompletionToolMessageParam |

### 4.2 消息结构

**system 消息**：
```python
{"role": "system", "content": "...system prompt..."}
```

**user 消息**：
```python
{"role": "user", "content": "...user input..."}
```

**assistant 消息（含工具调用）**：
```python
{
    "role": "assistant",
    "content": None,
    "tool_calls": [
        {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "knowledge_base",
                "arguments": "{\"query\": \"...\", \"search_type\": \"hybrid\"}"
            }
        }
    ]
}
```

**tool 消息（工具执行结果）**：
```python
{
    "role": "tool",
    "tool_call_id": "call_abc123",
    "content": "...tool execution result text..."
}
```

### 4.3 工具定义格式

工具以 OpenAI function tool 格式注册：

```python
{
    "type": "function",
    "function": {
        "name": "knowledge_base",
        "description": "...",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "..."},
                "search_type": {
                    "type": "string",
                    "enum": ["hybrid", "semantic", "keyword"],
                    "description": "..."
                }
            },
            "required": ["query"]
        }
    }
}
```

对应 openai SDK 类型：ChatCompletionToolParam（包含 type="function" 和 FunctionDefinition）。

## 5. StreamEvent

AgentLoop 产出的流式事件。密封的类型层次，每个子类型对应执行过程中的一种状态变化。

### 5.1 类型层次

```
StreamEvent (基类)
    PhaseEvent          执行阶段变化
    ToolCallEvent       LLM 决定调用某工具
    ToolResultEvent     工具执行完成
    SourceEvent         来源数据推送
    ContentEvent        LLM 产出文本增量
    DoneEvent           执行完成
    ErrorEvent          执行出错
```

### 5.2 各事件字段

**PhaseEvent**
- stage: str -- "thinking" | "calling_tool" | "generating"

**ToolCallEvent**
- tool_name: str
- tool_input: dict
- tool_call_id: str -- 对应 LLM 返回的 tool_call id

**ToolResultEvent**
- tool_name: str
- tool_call_id: str
- content_preview: str -- 工具返回内容的截断预览
- source_count: int

**SourceEvent**
- sources: List[SourceItem] -- 紧随 ToolResultEvent 产出

**ContentEvent**
- delta: str -- LLM 输出的文本片段

**DoneEvent**
- full_response: str -- 全部 delta 的拼接
- all_sources: List[SourceItem] -- 累积的全部来源

**ErrorEvent**
- code: str -- 错误代码
- message: str
- retriable: bool

ErrorEvent 的 code 取值：

| code | 含义 | retriable |
|------|------|-----------|
| max_iterations | 安全熔断触发 | False |
| llm_error | LLM API 错误（重试耗尽后） | True |
| cancelled | 外部取消 | False |
| internal_error | 未预期的内部错误 | False |

### 5.3 事件时序

典型的包含一次工具调用的序列：

```
PhaseEvent(thinking)
ToolCallEvent(knowledge_base, {query: "..."}, "call_abc123")
PhaseEvent(calling_tool)
ToolResultEvent(knowledge_base, "call_abc123", source_count=3)
SourceEvent([...])
PhaseEvent(thinking)
PhaseEvent(generating)
ContentEvent(delta) * N
DoneEvent
```

无工具调用的序列：

```
PhaseEvent(thinking)
PhaseEvent(generating)
ContentEvent(delta) * N
DoneEvent
```

工具执行失败后 LLM 决定直接回答的序列：

```
PhaseEvent(thinking)
ToolCallEvent(knowledge_base, {...}, "call_abc123")
PhaseEvent(calling_tool)
ToolResultEvent(knowledge_base, "call_abc123", source_count=0)  // error 情况
PhaseEvent(thinking)
PhaseEvent(generating)
ContentEvent(delta) * N
DoneEvent
```

## 6. ToolCallResult

工具执行的统一返回结构。

| 字段 | 含义 |
|------|------|
| tool_name | 工具名称 |
| tool_call_id | 对应 LLM 返回的 tool_call id |
| tool_input | 调用参数 |
| content | 文本内容，追加到消息链供 LLM 后续推理（作为 tool role 消息的 content） |
| sources | 来源元数据列表，不进入消息链，产出为 SourceEvent |
| error | 错误信息，仅在失败时有值 |

content 和 sources 的分离是关键设计：content 是给 LLM 看的（影响推理），sources 是给客户端看的（展示引用）。同一份工具输出被解析为两个用途不同的表示。

tool_call_id 用于将工具结果与 LLM 的 tool_call 请求关联。在 OpenAI 消息格式中，tool role 消息必须包含 tool_call_id 字段，指向对应 assistant 消息中的 tool_call.id。

## 7. SourceItem

单条引用来源的结构化表示。

| 字段 | 含义 |
|------|------|
| document_id | 来源文档标识 |
| chunk_id | 文档片段标识 |
| title | 文档标题 |
| text | 引用文本片段 |
| score | 检索相关性得分 |
| source_type | 来源类型（"retrieval" | "keyword" | "web_search"） |

沿用当前的 Source 格式，保持前端兼容性。source_type 增加 "keyword" 对应 ES 关键词搜索。

## 8. 生命周期

### 8.1 AgentLoop

每次请求创建，请求结束后丢弃。不跨请求存活，不需要考虑线程安全。

### 8.2 ModeConfig

每次请求由 ModeConfigFactory 生成。因为 RAGConfig 可能每次请求不同（用户调整了 top_k），配置需要反映当前请求的参数。

### 8.3 StreamEvent

AgentLoop 在执行过程中逐个产出，通过 AsyncGenerator yield 给调用方。调用方（API Router）消费后即可丢弃，不需要持久化。
