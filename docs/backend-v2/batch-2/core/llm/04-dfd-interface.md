# LLM 模块：数据流与接口定义

## 1. 上下文与范围

LLM 模块位于系统的底层：

- 上游：engine 模块（AgentLoop）通过 LLMClient 调用 LLM。context 模块（Compressor）通过 LLMClient 执行摘要生成。
- 下游：三个 Provider 的 OpenAI 兼容 API 端点。
- 同层：config 模块提供配置参数。

## 2. 数据流

### 2.1 非流式调用（AgentLoop 工具调用阶段）

```
AgentLoop
  |
  |  messages: List[ChatCompletionMessageParam]
  |  tools: List[ChatCompletionToolParam]
  |  tool_choice: str
  v
LLMClient.chat()
  |
  |  构造 create() 调用参数
  v
AsyncOpenAI.chat.completions.create(stream=False)
  |
  |  HTTP POST /v1/chat/completions
  v
Provider API
  |
  |  ChatCompletion（含 choices[0].message.tool_calls）
  v
LLMClient
  |
  |  ChatCompletion
  v
AgentLoop（解析 tool_calls，执行工具，追加消息，继续循环）
```

### 2.2 流式调用（AgentLoop 最终回答阶段）

```
AgentLoop
  |
  |  messages: List[ChatCompletionMessageParam]
  v
LLMClient.chat_stream()
  |
  |  构造 create(stream=True) 调用参数
  v
AsyncOpenAI.chat.completions.create(stream=True)
  |
  |  HTTP POST /v1/chat/completions（SSE 流）
  v
Provider API
  |
  |  AsyncStream[ChatCompletionChunk]
  v
LLMClient
  |
  |  AsyncIterator[ChatCompletionChunk]
  v
AgentLoop（逐 chunk 提取 delta.content，产出 ContentEvent）
```

### 2.3 摘要生成（Context 模块 Compressor）

```
Compressor
  |
  |  messages: List[ChatCompletionMessageParam]  (摘要 prompt + 历史消息)
  v
LLMClient.chat()
  |
  v
Provider API
  |
  |  ChatCompletion
  v
Compressor（提取 choices[0].message.content 作为摘要文本）
```

### 2.4 初始化数据流

```
应用启动
  |
  v
加载 llm.yaml 配置
  |
  v
读取环境变量（DASHSCOPE_API_KEY 等）
  |
  v
LLMClientFactory.create(provider="qwen")
  |
  |  构造 ProviderConfig
  |  创建 AsyncOpenAI(api_key=..., base_url=...)
  |  创建 LLMClient(client=AsyncOpenAI, config=...)
  v
注册为应用级单例
  |
  v
注入到 AgentLoop、Compressor 等组件
```

## 3. 接口定义

### 3.1 LLMClient

```python
class LLMClient:
    def __init__(
        self,
        client: AsyncOpenAI,
        model: str,
        default_params: dict,
    ) -> None: ...

    async def chat(
        self,
        messages: List[ChatCompletionMessageParam],
        tools: Optional[List[ChatCompletionToolParam]] = None,
        tool_choice: Optional[ChatCompletionToolChoiceOptionParam] = None,
        **kwargs,
    ) -> ChatCompletion: ...

    async def chat_stream(
        self,
        messages: List[ChatCompletionMessageParam],
        tools: Optional[List[ChatCompletionToolParam]] = None,
        tool_choice: Optional[ChatCompletionToolChoiceOptionParam] = None,
        **kwargs,
    ) -> AsyncIterator[ChatCompletionChunk]: ...
```

**构造参数说明：**

| 参数 | 类型 | 说明 |
|------|------|------|
| client | AsyncOpenAI | openai SDK 异步客户端实例 |
| model | str | 模型标识（如 "qwen3.5-plus"） |
| default_params | dict | 默认调用参数（temperature、max_tokens、top_p 等） |

**chat() 参数说明：**

| 参数 | 类型 | 说明 |
|------|------|------|
| messages | List[ChatCompletionMessageParam] | 消息列表（必填） |
| tools | List[ChatCompletionToolParam] | 工具定义列表 |
| tool_choice | ChatCompletionToolChoiceOptionParam | 工具选择策略 |
| **kwargs | dict | 覆盖默认参数（temperature、max_tokens 等） |

返回 ChatCompletion 对象。调用方从 choices[0].message 获取 LLM 的响应。

**chat_stream() 参数说明：**

与 chat() 相同。返回 AsyncIterator[ChatCompletionChunk]，调用方通过 `async for chunk in ...` 迭代。

**内部实现要点：**

```python
async def chat(self, messages, tools=None, tool_choice=None, **kwargs):
    params = {**self.default_params, **kwargs}
    create_kwargs = {
        "model": self.model,
        "messages": messages,
        **params,
    }
    if tools:
        create_kwargs["tools"] = tools
    if tool_choice:
        create_kwargs["tool_choice"] = tool_choice

    return await self.client.chat.completions.create(**create_kwargs)

async def chat_stream(self, messages, tools=None, tool_choice=None, **kwargs):
    params = {**self.default_params, **kwargs}
    create_kwargs = {
        "model": self.model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
        **params,
    }
    if tools:
        create_kwargs["tools"] = tools
    if tool_choice:
        create_kwargs["tool_choice"] = tool_choice

    stream = await self.client.chat.completions.create(**create_kwargs)
    async for chunk in stream:
        yield chunk
```

### 3.2 LLMClientFactory

```python
class LLMClientFactory:
    @staticmethod
    def create(
        provider: str = "qwen",
        model: Optional[str] = None,
        **override_params,
    ) -> LLMClient: ...
```

create() 逻辑：
1. 从 llm.yaml 读取 provider 对应的配置。
2. 从环境变量读取 api_key。
3. 用 override_params 覆盖默认参数。
4. 创建 AsyncOpenAI 实例。
5. 创建并返回 LLMClient。

### 3.3 DI 集成

```python
_llm_client: Optional[LLMClient] = None

async def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        config = load_llm_config()  # 从 llm.yaml 和环境变量加载
        _llm_client = LLMClientFactory.create(
            provider=config.provider,
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
        )
    return _llm_client
```

LLMClient 实例注入到：
- AgentLoop（通过 session 模块在创建 AgentLoop 时传入）
- Compressor（通过 context 模块在初始化时传入）

## 4. 配置文件格式

沿用当前 llm.yaml 格式，增加必要字段：

```yaml
llm:
  provider: qwen           # 当前活跃 Provider
  model: qwen3.5-plus      # 模型标识
  temperature: 0.7
  max_tokens: 32768
  top_p: 0.8
  timeout: 60              # 单次请求超时（秒）
  max_retries: 3           # SDK 网络层重试次数

  providers:
    qwen:
      base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
      api_key_env: DASHSCOPE_API_KEY
      default_model: qwen3.5-plus
    zhipu:
      base_url: https://open.bigmodel.cn/api/paas/v4
      api_key_env: ZHIPU_API_KEY
      default_model: glm-4.7-flash
    openai:
      base_url: https://api.openai.com/v1
      api_key_env: OPENAI_API_KEY
      default_model: gpt-4o-mini
```

顶层 provider 字段决定使用哪个 Provider。providers 字段列出所有可用 Provider 的配置。api_key 通过环境变量注入，不写入配置文件。

## 5. 数据所有权

| 数据 | 所有者 | LLM 模块的角色 |
|------|--------|---------------|
| 消息列表 (List[ChatCompletionMessageParam]) | context 模块 / AgentLoop | 消费者（原样传递给 API） |
| 工具定义 (List[ChatCompletionToolParam]) | tools 模块 / AgentLoop | 消费者（原样传递给 API） |
| ChatCompletion 响应 | Provider API | 中转者（从 API 获取后传递给调用方） |
| ChatCompletionChunk 流 | Provider API | 中转者 |
| LLMConfig | config 模块 | 消费者 |
| AsyncOpenAI 实例 | LLMClient | 持有者 |
