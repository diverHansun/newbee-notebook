# Core 模块重构设计文档

## 背景

当前 `core/engine/` 模块承担了过多职责：会话管理、上下文管理、模式分发、工具构建、流式处理。四种交互模式（Agent、Ask、Explain、Conclude）各自使用不同的 LlamaIndex 引擎，导致代码路径分裂、Source 收集不一致、流式行为不统一。

本次重构将 `core/engine/` 拆分为四个职责清晰的模块：

| 模块 | 职责 |
|------|------|
| **context** | 上下文管理：双轨内存模型、分层压缩、token 预算分配、消息链构建 |
| **engine** | 执行引擎：AgentLoop 工具调用循环、模式配置工厂、流式事件定义 |
| **session** | 会话管理：会话生命周期、消息持久化协调、并发控制 |
| **tools** | 工具层增强：新增 RAG Tool 封装（knowledge_base 工具），现有工具保留 |

## 模块依赖关系

```
session --> context                   session 调 context 读写历史
engine  --> context, tools            AgentLoop 从 context 取历史，从 tools 取工具
tools   --> rag                       RAG Tool 依赖 HybridRetriever
context --> llm (仅 tokenizer)        token 统计需要 tokenizer
```

禁止的依赖方向：

- context 不依赖 engine（不知道 AgentLoop 的存在）
- tools 不依赖 engine（不知道谁在调用工具）
- session 不依赖 engine（不知道 AgentLoop 的存在）
- rag 不依赖 tools（不知道自己被封装为工具）

## 与 LlamaIndex 的关系

重构后只依赖 LlamaIndex 的底层抽象，不再使用其高层框架：

- 保留：ChatMessage（消息格式）、LLM 接口（achat_with_tools）、BaseTool（工具抽象）、NodeWithScore（检索结果）
- 替换：ChatMemoryBuffer / ChatSummaryMemoryBuffer（由 context 模块取代）、FunctionAgent / ReActAgent / CondensePlusContextChatEngine（由 AgentLoop 取代）

## 文档索引

| 文档 | 说明 |
|------|------|
| [context/](./context/) | 上下文管理模块设计，建议首先阅读 |
| [engine/](./engine/) | 执行引擎模块设计，依赖 context 的概念 |
| [session/](./session/) | 会话管理模块设计，依赖 context |
| [tools/](./tools/) | 工具层增强设计，可独立阅读 |
| [migration-assessment.md](./migration-assessment.md) | 跨模块迁移评估，建议最后阅读 |

## 建议阅读顺序

context --> engine --> session --> tools --> migration-assessment
