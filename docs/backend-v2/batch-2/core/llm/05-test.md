# LLM 模块：验证策略

## 1. 测试范围

| 测试对象 | 覆盖 |
|---------|------|
| LLMClient.chat() 非流式调用 | 是 |
| LLMClient.chat_stream() 流式调用 | 是 |
| LLMClientFactory 配置加载 | 是 |
| Provider 配置差异 | 是 |
| 参数传递正确性 | 是 |

| 排除对象 | 理由 |
|---------|------|
| 工具调用循环逻辑 | 属于 engine 模块 |
| 消息链构建 | 属于 context 模块 |
| Provider API 行为 | 集成测试覆盖 |

## 2. 单元测试场景

### 2.1 LLMClient.chat()

**场景：正常非流式调用**

mock AsyncOpenAI.chat.completions.create()，传入消息列表和工具定义。验证：
- create() 被调用时 stream 参数为 False 或未传。
- messages、tools、tool_choice 被正确传递。
- 返回值为 mock 的 ChatCompletion 对象。

**场景：参数覆盖**

LLMClient 构造时 default_params 包含 temperature=0.7。调用 chat() 时传入 temperature=0.3。验证 create() 被调用时 temperature=0.3（kwargs 覆盖默认值）。

**场景：无工具调用**

不传 tools 参数。验证 create() 被调用时不包含 tools 和 tool_choice 参数。

**场景：指定 tool_choice**

传入 tool_choice="required"。验证 create() 被调用时 tool_choice="required"。

### 2.2 LLMClient.chat_stream()

**场景：正常流式调用**

mock AsyncOpenAI.chat.completions.create(stream=True)，返回 mock 的 AsyncStream。验证：
- create() 被调用时 stream=True。
- stream_options 包含 include_usage=True。
- 返回的异步迭代器产出 ChatCompletionChunk 序列。

**场景：流式 chunk 序列**

mock 返回 3 个 chunk（第一个含 role="assistant"，中间含 delta.content，最后一个 finish_reason="stop"）。验证迭代器按序产出所有 chunk。

**场景：空 delta.content**

mock 返回的部分 chunk 的 delta.content 为 None。验证 LLMClient 不过滤，原样传递（过滤逻辑由 AgentLoop 负责）。

### 2.3 LLMClientFactory

**场景：从配置创建 LLMClient**

提供 provider="qwen" 和对应配置。验证：
- AsyncOpenAI 的 base_url 为 DashScope 端点。
- api_key 从环境变量读取。
- LLMClient 的 model 为 "qwen3.5-plus"。

**场景：Provider 切换**

分别创建 qwen、zhipu、openai 三个 Provider 的 LLMClient。验证各自的 base_url 和默认 model 正确。

**场景：环境变量缺失**

不设置 api_key 环境变量。验证抛出明确的配置错误（不是 SDK 的模糊错误）。

**场景：参数覆盖**

调用 LLMClientFactory.create(provider="qwen", temperature=0.3)。验证 LLMClient 的 default_params 中 temperature=0.3。

### 2.4 配置加载

**场景：llm.yaml 加载**

提供完整的 llm.yaml 文件。验证 LLMConfig 各字段正确加载。

**场景：环境变量优先级**

llm.yaml 中 model="qwen-plus"，环境变量覆盖为 "qwen3.5-plus"。验证最终 model 为环境变量的值（如果支持环境变量覆盖）。

## 3. 集成测试

### 3.1 Provider 连通性

对每个 Provider 发起一次简单的 chat() 调用（"你好"）。验证：
- 返回 ChatCompletion 且 choices 非空。
- finish_reason 为 "stop"。
- usage 包含非零的 token 统计。

标记为慢测试，需要 API key。

### 3.2 工具调用集成

对 Qwen Provider 发起包含工具定义的 chat() 调用，prompt 明确要求调用工具。验证：
- finish_reason 为 "tool_calls"。
- message.tool_calls 非空。
- tool_call.function.name 匹配定义的工具名。
- tool_call.function.arguments 可解析为有效 JSON。

### 3.3 流式集成

对 Qwen Provider 发起 chat_stream() 调用。验证：
- 收到多个 ChatCompletionChunk。
- 第一个 chunk 含 delta.role="assistant"。
- 中间 chunk 含 delta.content 文本片段。
- 最后一个 chunk 含 finish_reason="stop"。
- 所有 delta.content 拼接后为完整回答。

### 3.4 tool_choice=required 集成

对 Qwen Provider 发起 tool_choice="required" 的 chat() 调用。验证：
- LLM 一定返回 tool_calls（不直接回答）。
- finish_reason 为 "tool_calls"。

## 4. 验证方法

单元测试使用 pytest + pytest-asyncio。Mock AsyncOpenAI 的 chat.completions.create() 方法。

mock 响应构造示例：

```python
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage

mock_response = ChatCompletion(
    id="chatcmpl-test",
    object="chat.completion",
    created=1234567890,
    model="qwen3.5-plus",
    choices=[Choice(
        index=0,
        message=ChatCompletionMessage(
            role="assistant",
            content="test response"
        ),
        finish_reason="stop"
    )],
    usage=CompletionUsage(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15
    )
)
```

测试文件：
```
tests/unit/core/llm/
    test_client.py          LLMClient chat/chat_stream 调用
    test_factory.py         LLMClientFactory 配置加载与创建
    test_config.py          LLMConfig 加载与验证
tests/integration/core/llm/
    test_providers.py       三个 Provider 的连通性与功能验证
```
