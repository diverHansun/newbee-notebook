# Engine 模块：验证策略

## 1. 测试范围

| 测试对象 | 覆盖 |
|---------|------|
| AgentLoop 核心循环 | 是 |
| 语义终止行为 | 是 |
| 四模式配置生成 | 是 |
| 流式事件序列 | 是 |
| Source 收集与累积 | 是 |
| 取消机制 | 是 |
| 安全熔断 | 是 |
| Explain/Conclude 检索策略 | 是 |
| 错误恢复策略 | 是 |

| 排除对象 | 理由 |
|---------|------|
| LLM Provider API 行为 | 属于 llm 模块的职责 |
| 工具实现逻辑 | 属于 tools 模块 |
| 消息链构建 | 属于 context 模块 |
| 消息持久化 | 属于 session 模块 |

## 2. 关键场景

### 2.1 AgentLoop 核心循环

**场景：单轮工具调用后生成回答**

mock LLMClient.chat() 第一轮返回包含 tool_calls 的 ChatCompletion（finish_reason="tool_calls"），LLMClient.chat_stream() 返回文本 chunk 序列。验证事件序列：PhaseEvent -> ToolCallEvent -> ToolResultEvent -> SourceEvent -> PhaseEvent -> ContentEvent* -> DoneEvent。

**场景：多轮工具调用**

mock LLMClient.chat() 连续两轮返回不同工具的 tool_calls，第三轮返回 finish_reason="stop"。验证两轮工具调用的 Source 都出现在 DoneEvent.all_sources 中。

**场景：LLM 直接回答（语义终止）**

mock LLMClient.chat() 第一轮即返回 finish_reason="stop"，无 tool_calls。验证无 ToolCallEvent 产出，DoneEvent.all_sources 为空。

**场景：安全熔断**

max_iterations=3，mock LLMClient.chat() 每轮都返回 tool_calls。验证执行 3 轮后产出 ErrorEvent(code="max_iterations")。

### 2.2 Explain / Conclude 检索循环

**场景：Explain 模式每轮都必须调用 knowledge_base**

config 的 `require_tool_every_iteration=True` 且 `required_tool_name="knowledge_base"`。验证某一轮若未返回 tool_call，runtime 追加 repair message 并要求模型重试该轮。

**场景：Conclude 模式最多 3 次 retrieval iteration**

mock 前两轮 `knowledge_base` 结果质量不足，第三轮后无论质量如何都进入 synthesis。验证不会继续第 4 次检索。

### 2.3 模式配置

**场景：四种模式的配置正确性**

对每种 mode 调用 ModeConfigFactory.build()，验证返回的工具列表、LoopPolicy、ToolPolicy、system_prompt 符合预期。

**场景：RAGConfig 参数传递**

传入 RAGConfig(top_k=10)，验证构建的 knowledge_base 工具内部使用 top_k=10。

**场景：Explain 模式的消息构造**

传入 selected_text，验证 ModeConfig.user_message 包含 selected_text 的构造消息。

**场景：source_document_ids 绑定**

传入 source_document_ids=["doc1", "doc2"]，验证 RAG/ES 工具的过滤参数包含这些 document_ids。

### 2.4 Source 与质量门控

**场景：工具返回 Source 和 quality_meta**

mock `knowledge_base` 返回包含 3 个检索结果的输出。验证 `ToolCallResult.sources` 包含 3 个 `SourceItem`，且 `quality_meta.quality_band` 被正确透传给 runtime。

**场景：多轮 Source 累积**

两轮工具调用分别返回 3 个和 2 个 source。验证 DoneEvent.all_sources 包含 5 个。

**场景：工具执行失败（错误恢复）**

mock 工具抛出异常。验证 AgentLoop 将错误信息作为 tool 消息追加到消息链，继续循环让 LLM 决定下一步。验证 ToolCallResult.error 有值，sources 为空。

### 2.5 错误恢复

**场景：工具执行失败后 LLM 决定直接回答**

mock 工具抛出异常，mock LLMClient.chat() 第二轮返回 finish_reason="stop"。验证 AgentLoop 将工具错误反馈给 LLM，LLM 不再调用工具，直接生成回答。事件序列中包含 ToolCallEvent、ToolResultEvent（error 标记），然后是 ContentEvent。

**场景：工具执行失败后 LLM 决定重试**

mock 工具第一次抛出异常，第二次成功。mock LLMClient.chat() 第二轮再次调用同一工具。验证 AgentLoop 允许 LLM 重试工具调用，最终成功获取结果。

**场景：LLM API 429 重试成功**

mock LLMClient.chat() 第一次抛出 429 错误，第二次成功。验证 AgentLoop 在指数退避后重试成功，正常继续循环。

**场景：LLM API 重试耗尽**

mock LLMClient.chat() 连续 3 次抛出 500 错误。验证 AgentLoop 产出 ErrorEvent(code="llm_error", retriable=True)。

**场景：tool_calls JSON 解析失败**

mock LLMClient.chat() 返回的 tool_call.function.arguments 为非法 JSON。验证 AgentLoop 将解析错误反馈给 LLM，LLM 第二次返回正确的 JSON。

**场景：JSON 修正失败**

mock LLMClient.chat() 连续返回非法 JSON 超过 json_fix_max_attempts 次。验证 AgentLoop 产出 ErrorEvent(code="internal_error")。

### 2.6 取消

**场景：工具调用间取消**

第一轮工具执行完成后、第二轮开始前调用 cancel()。验证停止执行，DoneEvent 包含第一轮的 Source。

### 2.7 流式输出

**场景：ContentEvent 的 delta 拼接**

mock LLMClient.chat_stream() 返回多个 chunk，每个 chunk 含 delta.content。验证所有 ContentEvent.delta 拼接后等于 DoneEvent.full_response。

**场景：空 delta 过滤**

mock LLMClient.chat_stream() 返回部分 chunk 的 delta.content 为 None。验证不产出空 ContentEvent。

## 3. 集成测试

### 3.1 LLM Provider 集成

使用实际 Qwen LLM 验证：tool_choice=auto/required 的行为、流式生成的正确性。标记为慢测试。通过 LLMClient 调用，验证 OpenAI 兼容端点的 tool_calls 格式符合预期。

### 3.2 端到端 SSE

使用 httpx SSE 客户端发送请求到 /chat/stream 端点，验证事件类型和顺序符合协议、content delta 拼接后等于完整回答、sources 包含有效引用。

## 4. 验证方法

单元测试使用 pytest + pytest-asyncio。Mock LLMClient 的 chat() 和 chat_stream() 方法，控制返回 ChatCompletion（含 tool_calls）或文本 chunk 序列。Mock 工具的 execute() 返回预设 ToolCallResult。

mock LLMClient 返回值构造示例：

```python
# 模拟包含 tool_calls 的响应
mock_response = ChatCompletion(
    id="chatcmpl-test",
    object="chat.completion",
    created=1234567890,
    model="qwen-plus",
    choices=[Choice(
        index=0,
        message=ChatCompletionMessage(
            role="assistant",
            content=None,
            tool_calls=[ChatCompletionMessageToolCall(
                id="call_abc123",
                type="function",
                function=Function(
                    name="knowledge_base",
                    arguments='{"query": "test", "search_type": "hybrid"}'
                )
            )]
        ),
        finish_reason="tool_calls"
    )]
)

# 模拟无 tool_calls 的响应（语义终止）
mock_stop_response = ChatCompletion(
    id="chatcmpl-test2",
    object="chat.completion",
    created=1234567890,
    model="qwen-plus",
    choices=[Choice(
        index=0,
        message=ChatCompletionMessage(
            role="assistant",
            content=None,
            tool_calls=None
        ),
        finish_reason="stop"
    )]
)
```

测试文件：
```
tests/unit/core/engine/
    test_agent_loop.py          核心循环、语义终止、安全熔断、取消
    test_error_recovery.py      错误恢复策略（工具失败、LLM 重试、JSON 修正）
    test_mode_config.py         ModeConfigFactory 配置生成
    test_stream_events.py       事件序列化
tests/integration/core/engine/
    test_agent_loop_llm.py      AgentLoop + 真实 LLM Provider
tests/integration/api/
    test_chat_stream_sse.py     端到端 SSE
```
