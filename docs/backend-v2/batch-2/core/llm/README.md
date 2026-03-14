# LLM 模块设计文档

## 概述

LLM 模块提供轻量的 LLMClient 抽象，基于 openai Python SDK 的 AsyncOpenAI 封装 LLM 调用能力。所有 Provider（Qwen/DashScope、Zhipu、OpenAI）通过 OpenAI 兼容的 `/v1/chat/completions` 端点接入，统一为相同的调用接口。

核心设计原则：
- **薄封装**：LLMClient 是 AsyncOpenAI 的薄封装，不引入额外抽象层。openai SDK 已经提供了完善的类型定义、重试机制和流式支持。
- **Provider 透明**：上层调用者（AgentLoop）不感知具体使用哪个 Provider，只通过 LLMClient 接口调用。
- **脱离 LlamaIndex**：执行层（engine）和 LLM 调用层不再依赖 LlamaIndex。LlamaIndex 保留在 RAG 检索层和 Embedding 层。
- **Chat Completions 作为内部真源**：batch-2 第一版固定以 OpenAI-compatible Chat Completions message/tool schema 作为内部标准，不以 provider 自定义 Responses API 或事件流作为 runtime 内部真源。
- **thinking 差异由 LLMClient 吸收**：Qwen/Zhipu 的 `reasoning_content`、thinking 开关和流式细节由 `LLMClient` 处理，不让 `engine/context/session` 直接感知 provider 细节。

## 文档索引

| 文档 | 说明 |
|------|------|
| [01-goals-duty.md](./01-goals-duty.md) | 设计目标与职责边界 |
| [02-architecture.md](./02-architecture.md) | LLMClient 架构、Provider 配置、LlamaIndex 脱离边界 |
| [03-data-model.md](./03-data-model.md) | OpenAI SDK 类型参考、LLMConfig、Provider 配置 |
| [04-dfd-interface.md](./04-dfd-interface.md) | LLMClient 接口定义、数据流、DI 集成 |
| [05-test.md](./05-test.md) | 验证策略 |
| [06-message-contract.md](./06-message-contract.md) | 内部统一消息协议：OpenAI-compatible message contract |

## 模块关系

| 关联模块 | 关系 |
|---------|------|
| engine | AgentLoop 通过 LLMClient 接口调用 LLM |
| context | context 模块的 Compressor 使用 LLMClient 执行摘要生成 |
| config | 读取 llm.yaml 和环境变量获取 Provider 配置 |

## 与当前实现的对比

| 维度 | 当前实现 | 重构后 |
|------|---------|--------|
| 基础框架 | LlamaIndex OpenAI 适配器 | openai SDK AsyncOpenAI |
| 抽象层次 | LlamaIndex LLM 抽象（achat_with_tools / astream_chat） | LLMClient（chat / chat_stream） |
| Provider 适配 | QwenOpenAI / ZhipuOpenAI 继承 LlamaIndex OpenAI | Provider 配置驱动，同一个 AsyncOpenAI 类 |
| 消息格式 | LlamaIndex ChatMessage | OpenAI-compatible 内部消息协议 |
| 工具调用 | LlamaIndex achat_with_tools 封装 | 直接传 tools 参数给 chat completions API |

## 当前冻结的 batch-2 边界

- tool-using 请求默认不依赖 provider thinking mode 作为核心执行能力
- `reasoning_content` 只作为 runtime transient signal，不进入持久化消息
- provider 差异由 `LLMClient` 吸收，业务层只消费统一的 message/tool contract
