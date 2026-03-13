# Core 模块重构设计文档

## 背景

当前 `core/engine/` 模块承担了过多职责：会话管理、上下文管理、模式分发、工具构建、流式处理。四种交互模式（Agent、Ask、Explain、Conclude）各自使用不同的 LlamaIndex 引擎，导致代码路径分裂、Source 收集不一致、流式行为不统一。

本次重构将 `core/engine/` 拆分为五个职责清晰的模块：

| 模块 | 职责 |
|------|------|
| **llm** | LLM 调用层：LLMClient 基于 openai SDK AsyncOpenAI，Provider 配置管理 |
| **context** | 上下文管理：双轨内存模型、分层压缩、token 预算分配、消息链构建 |
| **engine** | 执行引擎：统一 workflow runtime、ModeConfigFactory、LoopPolicy / ToolPolicy、StreamEvent 定义 |
| **session** | 会话管理：会话生命周期、消息持久化协调、并发控制 |
| **tools** | 工具层：ToolRegistry 统一注册中心、BuiltinToolProvider、knowledge_base 工具封装 |

## 模块依赖关系

```
session --> engine, context       session 创建 AgentLoop，调 context 读写历史
engine  --> llm, tools            AgentLoop 通过 LLMClient 调 LLM，使用 ToolDefinition 列表
tools   --> mcp                   ToolRegistry 合并内置工具和 MCP 工具
context --> llm                   Compressor 使用 LLMClient 生成摘要
llm     --> config                从 llm.yaml 和环境变量加载配置
```

禁止的依赖方向：

- context 不依赖 engine（不知道 AgentLoop 的存在）
- tools 不依赖 engine（不知道谁在调用工具）
- llm 不依赖 engine（不知道谁在调用 LLMClient）
- session 不直接依赖 llm（通过 engine 间接使用）

## 与 LlamaIndex 的关系

重构后 engine 和 LLM 调用层脱离 LlamaIndex，RAG/Embedding 层保留：

- **移除依赖**：FunctionAgent / ReActAgent / CondensePlusContextChatEngine（由统一 runtime 取代）、ChatMemoryBuffer / ChatSummaryMemoryBuffer（由 context 模块取代）、LlamaIndex LLM 接口 achat_with_tools / astream_chat（由 LLMClient chat / chat_stream 取代）、ChatMessage 消息格式（由 OpenAI 兼容 dict 取代）
- **保留依赖**：pgvector VectorStoreIndex（向量存储和检索）、HybridRetriever（混合检索）、NodeWithScore（检索结果）、Embedding 模型管理

## 文档索引

| 文档 | 说明 |
|------|------|
| [llm/](./llm/) | LLM 调用层设计：LLMClient、Provider 配置、OpenAI SDK 类型参考 |
| [context/](./context/) | 上下文管理模块设计：双轨内存、最小版截断策略、后续压缩演进 |
| [engine/](./engine/) | 执行引擎模块设计：workflow runtime、mode matrix、retrieval quality gates、StreamEvent |
| [session/](./session/) | 会话管理模块设计 |
| [tools/](./tools/) | 工具层设计：ToolRegistry、BuiltinToolProvider、knowledge_base、统一工具协议 |
| [migration-assessment.md](./migration-assessment.md) | 跨模块迁移评估，建议最后阅读 |

## 建议阅读顺序

llm --> tools --> context --> engine --> session --> migration-assessment
