# Engine 模块设计文档

## 概述

Engine 模块是 AgentLoop 执行引擎。它接收构建好的消息链（OpenAI 兼容格式）和工具列表，通过 LLMClient 驱动 LLM 进行工具调用循环，产出流式事件序列。

核心设计原则：
- **语义终止**：循环由 LLM 决定何时结束，max_iterations 仅作安全熔断。
- **配置驱动**：四种模式共享同一个 AgentLoop，差异通过 ModeConfigFactory 配置体现。
- **错误恢复**：不同类型错误采用不同恢复策略，而非统一中断。

重构后 engine 模块只包含执行逻辑，不包含会话管理（由 session 负责）和上下文管理（由 context 负责）。LLM 调用通过轻量 LLMClient 接口（基于 openai SDK），脱离 LlamaIndex 依赖。

## 文档索引

| 文档 | 说明 |
|------|------|
| [01-goals-duty.md](./01-goals-duty.md) | 设计目标（语义终止、错误恢复）与职责边界 |
| [02-architecture.md](./02-architecture.md) | AgentLoop + LLMClient 架构、错误恢复策略、LlamaIndex 脱离 |
| [03-data-model.md](./03-data-model.md) | AgentLoopConfig、OpenAI 消息格式、StreamEvent、ToolCallResult |
| [04-dfd-interface.md](./04-dfd-interface.md) | AgentLoop 接口、核心循环伪代码、SSE 事件协议、取消与错误恢复数据流 |
| [05-test.md](./05-test.md) | 验证策略（含错误恢复测试场景） |

## 模块关系

| 依赖模块 | 关系 |
|---------|------|
| llm | AgentLoop 通过 LLMClient 接口调用 LLM |
| tools / ToolRegistry | 提供 ToolDefinition 列表 |
| context | 提供 OpenAI 兼容格式的消息链 |
| session | 调用 AgentLoop，消费 StreamEvent |
| API Router | 将 StreamEvent 转换为 SSE 推送 |
