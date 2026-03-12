# LLM 模块：架构设计

## 1. 架构总览

```
LLMClient                 统一调用接口（chat / chat_stream）
    |
AsyncOpenAI               openai SDK 异步客户端
    |
OpenAI-compatible API     /v1/chat/completions
    |
Provider                  Qwen(DashScope) / Zhipu / OpenAI
```

LLMClient 是 AsyncOpenAI 的薄封装。不同 Provider 的差异仅体现在 AsyncOpenAI 的构造参数上（api_key、base_url），调用方法完全一致。

### 1.1 对比当前实现

| 维度 | 当前实现 | 重构后 |
|------|---------|--------|
| 基础类 | LlamaIndex OpenAI | openai AsyncOpenAI |
| Provider 适配 | QwenOpenAI 继承、ZhipuOpenAI 继承，各约 100 行 | 同一 AsyncOpenAI，仅配置不同 |
| 注册机制 | @register_llm 装饰器 + builder 函数 | LLMClientFactory.create(provider) |
| 消息格式 | LlamaIndex ChatMessage | OpenAI dict（ChatCompletionMessageParam） |
| 工具调用 | achat_with_tools（LlamaIndex 封装） | 直接 chat completions + tools 参数 |
| 流式调用 | astream_chat（LlamaIndex 封装） | chat completions + stream=True |

## 2. 设计决策

### 2.1 不继承、不扩展 AsyncOpenAI

LLMClient 持有 AsyncOpenAI 实例（组合），而非继承它。理由：
- AsyncOpenAI 的公开 API 远大于 LLMClient 需要暴露的接口（chat / chat_stream 两个方法）。继承会泄露不必要的接口。
- LLMClient 可以在内部统一处理日志记录、usage 信息提取等横切关注点。

### 2.2 Provider 配置统一

三个 Provider 的差异完全可以用配置参数表达：

| Provider | base_url | api_key 来源 | 默认 model |
|----------|----------|-------------|-----------|
| qwen | https://dashscope.aliyuncs.com/compatible-mode/v1 | DASHSCOPE_API_KEY | qwen3.5-plus |
| zhipu | https://open.bigmodel.cn/api/paas/v4 | ZHIPU_API_KEY | glm-4.7-flash |
| openai | https://api.openai.com/v1（默认） | OPENAI_API_KEY | gpt-4o-mini |

不需要为每个 Provider 创建子类。当前实现中 QwenOpenAI 和 ZhipuOpenAI 的自定义逻辑（context window 查询、tokenizer 适配）属于 LlamaIndex 框架的要求，脱离 LlamaIndex 后不再需要。

### 2.3 工厂模式

LLMClientFactory 根据 provider 名称和配置参数创建 LLMClient 实例。配置来源优先级：

1. 调用参数（代码中显式传入）
2. 环境变量（DASHSCOPE_API_KEY、ZHIPU_API_KEY 等）
3. 配置文件（llm.yaml）
4. 默认值

### 2.4 保留 LlamaIndex 用于 RAG/Embedding

LlamaIndex 在 RAG 检索层的价值：
- pgvector VectorStoreIndex：向量存储和检索的成熟抽象。
- HybridRetriever：混合检索（语义 + 关键词）的组合逻辑。
- Embedding 模型管理：嵌入模型的统一接口和缓存。

这些功能与 LLM 调用层正交，保留不影响 engine 模块的解耦。RAG 工具内部使用 LlamaIndex 进行检索，engine 模块不感知。

## 3. 模块结构与文件布局

```
core/llm/
    __init__.py             公开接口导出
    client.py               LLMClient 类
    config.py               LLMConfig、ProviderConfig 数据类
    factory.py              LLMClientFactory 工厂
```

### 3.1 文件职责

**client.py** -- LLM 客户端

LLMClient 类，持有 AsyncOpenAI 实例。暴露 chat() 和 chat_stream() 两个方法。内部处理日志记录和 usage 提取。

**config.py** -- 配置数据类

LLMConfig 和 ProviderConfig 数据类。LLMConfig 包含当前活跃 Provider 的配置。ProviderConfig 包含单个 Provider 的连接参数。

**factory.py** -- 工厂

LLMClientFactory 读取配置文件和环境变量，根据 provider 名称创建 LLMClient 实例。

## 4. 架构约束

### 4.1 OpenAI 兼容性要求

所有 Provider 必须提供 OpenAI 兼容的 `/v1/chat/completions` 端点。当前三个 Provider 均满足。如果未来接入不兼容的 Provider，需要在 LLMClient 层面做适配（如请求/响应格式转换），但不影响 engine 模块。

### 4.2 API 特性差异

不同 Provider 对 OpenAI API 特性的支持程度不同：

| 特性 | Qwen | Zhipu | OpenAI |
|------|------|-------|--------|
| tool_choice="required" | 支持 | 支持 | 支持 |
| parallel_tool_calls | 支持 | 支持 | 支持 |
| stream_options.include_usage | 支持 | 支持 | 支持 |
| max_completion_tokens | 部分模型 | 需确认 | 支持 |

对于不支持的特性，LLMClient 静默忽略（不传该参数），而非报错。具体的兼容性处理在 LLMClient 内部完成。

### 4.3 超时与重试

- **连接级超时**：通过 AsyncOpenAI 的 timeout 参数设置（默认 60s）。
- **连接级重试**：通过 AsyncOpenAI 的 max_retries 参数设置（默认 3）。这是 SDK 内置的网络层重试。
- **业务级重试**：由 AgentLoop 实现（指数退避），处理 429、500 等 API 错误。LLMClient 不做业务重试。
