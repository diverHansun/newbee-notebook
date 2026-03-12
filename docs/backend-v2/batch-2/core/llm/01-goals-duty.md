# LLM 模块：设计目标与职责边界

## 1. 设计目标

### 1.1 薄封装

LLMClient 是 openai SDK AsyncOpenAI 的薄封装，不引入额外抽象层。openai SDK 已提供：
- 完善的请求/响应类型定义（ChatCompletion、ChatCompletionChunk 等）。
- 内置重试机制（max_retries 参数）。
- 流式支持（AsyncStream[ChatCompletionChunk]）。
- 超时控制（timeout 参数）。

LLMClient 的职责是将 Provider 配置（api_key、base_url、model 等）封装为一个可注入的实例，而非重新实现 SDK 已有的能力。

### 1.2 Provider 透明

上层调用者（AgentLoop、Compressor）通过 LLMClient 接口调用 LLM，不感知具体使用哪个 Provider。三个 Provider（Qwen、Zhipu、OpenAI）的差异仅体现在配置参数上，调用接口完全一致。

### 1.3 脱离 LlamaIndex

当前 LLM 调用层基于 LlamaIndex 的 OpenAI 适配器（QwenOpenAI、ZhipuOpenAI 继承 LlamaIndex OpenAI 类）。重构后直接使用 openai SDK，消除 LlamaIndex 在执行层的依赖。

脱离边界：
- **移除 LlamaIndex**：LLM 调用层（chat / chat_stream）、消息格式（改用 OpenAI 兼容 dict）。
- **保留 LlamaIndex**：RAG 检索层（pgvector VectorStoreIndex、HybridRetriever）、Embedding 层。这些是 LlamaIndex 的核心价值所在，保留可以复用其成熟的向量检索和索引管理能力。

### 1.4 配置驱动

Provider 选择和参数配置通过 llm.yaml 配置文件和环境变量驱动。新增 Provider 只需添加一组配置，不需要新建类文件。

## 2. 职责

### 2.1 LLM 调用

提供非流式（chat）和流式（chat_stream）两个调用方法。接收 OpenAI 兼容格式的消息列表、工具定义、tool_choice 等参数，返回 openai SDK 的标准响应类型。

### 2.2 Provider 配置管理

管理三个 Provider 的连接参数（api_key、base_url、model、temperature 等）。从 llm.yaml 和环境变量读取配置，构建 AsyncOpenAI 实例。

### 2.3 模型参数传递

将调用参数（temperature、max_tokens、top_p 等）传递给底层 API。不做参数校验（由 API 端校验），不做参数变换。

## 3. 非职责

### 3.1 工具调用逻辑

LLMClient 不解析 tool_calls、不执行工具、不管理工具调用循环。它只负责将请求发送给 LLM API 并返回原始响应。工具调用逻辑由 AgentLoop 处理。

### 3.2 消息链管理

LLMClient 不构建、不修改、不压缩消息链。它接收完整的消息列表作为参数。消息链管理由 context 模块负责。

### 3.3 重试策略

LLMClient 不实现业务层面的重试策略。openai SDK 内置了连接级重试（max_retries），业务层面的重试（如 AgentLoop 的指数退避重试）由调用方实现。

### 3.4 Token 计数

LLMClient 不做 token 计数或预算管理。Token 计数由 context 模块的 TokenCounter 负责。LLMClient 只将 API 响应中的 usage 信息（prompt_tokens、completion_tokens）透传给调用方。

### 3.5 流式事件转换

LLMClient 不将 ChatCompletionChunk 转换为 StreamEvent。流式 chunk 的消费和事件转换由 AgentLoop 负责。
