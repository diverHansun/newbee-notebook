# Engine 模块：数据流与接口定义

## 1. 上下文与范围

Engine 模块位于系统的中间层：

- 上游：session 模块调用 engine 执行交互。API Router 消费 engine 产出的 StreamEvent。
- 下游：LLMClient（llm 模块）和 tools 模块，作为 AgentLoop 的执行依赖。
- 同层：context 模块提供消息链（OpenAI 兼容格式），ToolRegistry 提供工具列表。

## 2. 端到端数据流

### 2.1 主流程

一次完整的交互数据流（以 Agent 模式为例）：

1. session 模块接收请求，调用 ToolRegistry.get_tools(mode) 获取工具列表。
2. session 模块调用 ModeConfigFactory.build(mode, tools, rag_config, ...) 获取 ModeConfig。
3. session 模块调用 context 模块的 ContextBuilder.build(track="main", system_prompt) 获取消息链（OpenAI 兼容格式）。
4. session 模块创建 AgentLoop 实例，传入 LLMClient、ModeConfig.tools、ModeConfig.agent_loop_config。
5. 调用 AgentLoop.stream(user_message, chat_history)。
6. AgentLoop 进入循环：
   - 将 system_prompt + chat_history + user_message 组装为完整消息列表。
   - 调用 LLMClient.chat(messages, tools, tool_choice) 获取 ChatCompletion 响应。
   - 检查响应中 choice.finish_reason 和 message.tool_calls。
   - 有 tool_calls：执行工具，收集 ToolCallResult，将 assistant 消息和 tool 消息追加到消息列表，产出事件，继续循环。
   - 无 tool_calls（finish_reason="stop"）：调用 LLMClient.chat_stream(messages) 重新发起流式请求，逐 chunk 产出 ContentEvent。
7. AgentLoop 产出 DoneEvent，执行结束。
8. session 模块将新消息写入 context 模块，并协调持久化。

### 2.2 最终回答的流式输出

当 AgentLoop 检测到 LLM 不再调用工具（非流式 chat() 返回的 finish_reason="stop"）时，需要获取 LLM 的流式文本输出。实现方式：

用相同的消息列表调用 LLMClient.chat_stream()，获得 AsyncIterator[ChatCompletionChunk]。遍历 chunk，提取 delta.content 产出 ContentEvent。

这意味着最终回答阶段有一次额外的 LLM 调用（非流式判断 + 流式输出）。但相比当前 ChatMode 的两阶段策略（完整非流式 agent 执行 + 完整流式润色），减少了一次完整的 LLM 推理。

备选方案：在工具调用阶段也使用流式，通过解析 delta 中的 tool_calls 判断。这可以避免额外调用，但增加了流式解析 tool_call JSON 的复杂度（需要累积 arguments 片段并解析）。当前选择非流式工具阶段 + 流式回答阶段的方案，优先保证实现简洁。

### 2.3 Explain/Conclude 的差异

- ModeConfigFactory 将 selected_text 组装为 user_message。
- AgentLoopConfig 的 tool_choice 为 "required"。
- 第一轮 LLM 被强制调用工具，AgentLoop 在工具执行后将 tool_choice 切回 "auto"。
- 第二轮 LLM 基于检索结果生成回答（语义终止）。
- context 模块构建消息链时注入 Main 轨道历史（inject_main=True）。

### 2.4 取消数据流

两条路径：

**客户端关闭 SSE 连接：** API Router 检测到断开 -> 调用 AgentLoop.cancel() -> AgentLoop 在下一个检查点停止 -> 产出 DoneEvent（含部分结果）。

**主动取消请求：** 客户端发送 cancel 请求 -> session 模块找到活跃的 AgentLoop -> 调用 cancel() -> 同上。

检查点位置：每次循环迭代开始前、多个 tool_calls 的执行间隙。不在 LLM 调用进行中或单个工具执行进行中检查。

### 2.5 错误恢复数据流

**工具执行失败：**
```
AgentLoop 调用工具 -> 工具抛出异常 -> AgentLoop 构造错误 tool 消息 -> 追加到消息链 -> 继续循环（LLM 收到错误信息后自行决定）
```

消息链中的错误 tool 消息格式：
```python
{
    "role": "tool",
    "tool_call_id": "call_abc123",
    "content": "Error: tool execution failed: <error message>"
}
```

**LLM API 错误：**
```
AgentLoop 调用 LLMClient.chat() -> 抛出异常 -> 指数退避重试 -> 成功则继续循环 / 失败则产出 ErrorEvent
```

**JSON 解析失败：**
```
LLM 返回 tool_calls -> arguments 解析失败 -> 构造反馈消息追加到消息链 -> 继续循环（LLM 修正格式）
```

## 3. 接口定义

### 3.1 AgentLoop

```python
class AgentLoop:
    def __init__(
        self,
        llm_client: LLMClient,
        system_prompt: str,
        tools: List[ToolDefinition],
        config: AgentLoopConfig,
    ) -> None: ...

    async def stream(
        self,
        message: str,
        chat_history: List[ChatCompletionMessageParam],
    ) -> AsyncGenerator[StreamEvent, None]: ...

    async def run(
        self,
        message: str,
        chat_history: List[ChatCompletionMessageParam],
    ) -> AgentResult: ...

    def cancel(self) -> None: ...
```

参数说明：

- `llm_client`：LLMClient 实例，由 llm 模块提供。AgentLoop 通过此接口调用 LLM。
- `system_prompt`：系统提示词，由 ModeConfig 提供。
- `tools`：工具定义列表。每个 ToolDefinition 包含 OpenAI function tool 格式的元数据和可调用的执行函数。
- `config`：AgentLoopConfig 实例。
- `message`：当前用户消息（或 Explain/Conclude 的构造消息）。
- `chat_history`：context 模块构建的消息链，OpenAI 兼容格式。

AgentResult 是 run() 的返回值：

| 字段 | 类型 | 含义 |
|------|------|------|
| response | str | 完整回答文本 |
| sources | List[SourceItem] | 全部来源 |
| tool_calls_made | List[str] | 调用过的工具名列表 |
| iterations | int | 循环次数 |

### 3.2 ToolDefinition

AgentLoop 看到的工具描述。将 OpenAI function tool 元数据和实际执行函数绑定。

```python
class ToolDefinition:
    name: str                          # 工具名称
    description: str                   # 工具描述
    parameters: dict                   # JSON Schema 参数定义
    execute: Callable[[dict], Awaitable[ToolCallResult]]  # 异步执行函数
```

ToolDefinition 的 name / description / parameters 用于构造发送给 LLM 的 ChatCompletionToolParam：

```python
{
    "type": "function",
    "function": {
        "name": tool_def.name,
        "description": tool_def.description,
        "parameters": tool_def.parameters
    }
}
```

execute 函数接收 LLM 返回的 arguments（解析后的 dict），返回 ToolCallResult。

### 3.3 ModeConfigFactory

```python
class ModeConfigFactory:
    @staticmethod
    def build(
        mode: ModeType,
        tools: List[ToolDefinition],
        rag_config: Optional[RAGConfig] = None,
        source_document_ids: Optional[List[str]] = None,
        selected_text: Optional[str] = None,
    ) -> ModeConfig: ...
```

参数说明：
- `tools`：由 ToolRegistry.get_tools(mode) 获取的工具列表。
- `rag_config`：前端传入的 RAG 参数。ModeConfigFactory 将其绑定到 RAG/ES 工具的配置中。
- `source_document_ids`：前端选择的文档范围。绑定到 RAG/ES 工具的过滤参数中。
- `selected_text`：Explain/Conclude 模式的选中文本，用于构造 user_message。

### 3.4 SSE 事件协议

StreamEvent 到 SSE 的映射由 API Router 层执行。每个 SSE 事件由 event 行和 data 行组成：

```
event: {event_type}
data: {json_payload}

```

事件类型映射：

| StreamEvent | SSE event | data schema |
|------------|-----------|-------------|
| PhaseEvent | phase | {"stage": "thinking"} |
| ToolCallEvent | tool_call | {"tool_name": "...", "tool_input": {...}} |
| ToolResultEvent | tool_result | {"tool_name": "...", "content_preview": "...", "source_count": N} |
| SourceEvent | sources | {"sources": [...]} |
| ContentEvent | content | {"delta": "..."} |
| DoneEvent | done | {} |
| ErrorEvent | error | {"code": "...", "message": "...", "retriable": bool} |

心跳事件（heartbeat）由 API Router 层独立注入（每 15 秒），不属于 AgentLoop 的产出。

与当前 SSE 格式的对照：

| 当前 | 重构后 | 变化 |
|------|--------|------|
| start | phase(thinking) | 合并 |
| thinking | phase | stage 值更明确 |
| content | content | 不变 |
| sources | sources | 改为紧随 tool_result 发送 |
| done | done | 不变 |
| error | error | 新增 code 和 retriable |
| heartbeat | heartbeat | 不变（API 层注入） |
| -- | tool_call | 新增 |
| -- | tool_result | 新增 |

### 3.5 HTTP API

统一流式端点保持不变：

```
POST /api/v1/notebooks/{notebook_id}/chat/stream
```

请求体扩展：

| 字段 | 类型 | 说明 |
|------|------|------|
| session_id | string | 会话标识 |
| mode | string | "agent" / "ask" / "explain" / "conclude" |
| message | string, optional | Agent/Ask 必填 |
| selected_text | string, optional | Explain/Conclude 必填 |
| source_document_ids | list[string], optional | 文档范围过滤 |
| rag_config | object, optional | RAG 参数覆盖 |

校验规则：mode 为 agent/ask 时 message 必填；mode 为 explain/conclude 时 selected_text 必填。

## 4. 数据所有权

| 数据 | 所有者 | Engine 的角色 |
|------|--------|--------------|
| 消息链 (List[ChatCompletionMessageParam]) | context 模块 | 消费者（接收后在循环中追加） |
| 工具列表 (List[ToolDefinition]) | ToolRegistry / tools 模块 | 消费者 |
| LLMClient 实例 | llm 模块 | 消费者 |
| StreamEvent 序列 | AgentLoop | 生产者 |
| SourceItem | 工具执行结果 | 中转者（从工具提取后传递给上层） |
| ModeConfig | ModeConfigFactory | 生产者（每请求创建） |

## 5. AgentLoop 核心循环伪代码

```python
async def stream(self, message, chat_history):
    messages = [
        {"role": "system", "content": self.system_prompt},
        *chat_history,
        {"role": "user", "content": message},
    ]
    tool_choice = self.config.tool_choice
    all_sources = []
    iteration = 0

    while iteration < self.config.max_iterations:
        if self._cancelled:
            break

        iteration += 1
        yield PhaseEvent(stage="thinking")

        # 非流式调用 LLM
        response = await self._call_llm_with_retry(messages, tool_choice)
        choice = response.choices[0]

        if not choice.message.tool_calls:
            # 语义终止：LLM 不再调用工具，进入流式输出
            break

        # 处理工具调用
        assistant_msg = self._build_assistant_message(choice.message)
        messages.append(assistant_msg)

        for tool_call in choice.message.tool_calls:
            yield ToolCallEvent(...)
            yield PhaseEvent(stage="calling_tool")

            result = await self._execute_tool(tool_call)
            tool_msg = {"role": "tool", "tool_call_id": tool_call.id, "content": result.content}
            messages.append(tool_msg)

            yield ToolResultEvent(...)
            if result.sources:
                all_sources.extend(result.sources)
                yield SourceEvent(sources=result.sources)

        # 首轮 required 后切回 auto
        if tool_choice == "required":
            tool_choice = "auto"
    else:
        # max_iterations 安全熔断
        yield ErrorEvent(code="max_iterations", ...)
        return

    # 流式输出最终回答
    yield PhaseEvent(stage="generating")
    full_response = ""
    async for chunk in self.llm_client.chat_stream(messages):
        delta = chunk.choices[0].delta
        if delta.content:
            full_response += delta.content
            yield ContentEvent(delta=delta.content)

    yield DoneEvent(full_response=full_response, all_sources=all_sources)
```

此伪代码省略了错误恢复、取消检查等细节，仅展示核心数据流。
