# Context 模块设计文档

## 概述

Context 模块负责管理对话上下文：维护双轨内存模型、执行分层压缩、分配 token 预算、构建供 AgentLoop 消费的消息链。

它是 engine 和 session 模块的共同依赖——engine 从它获取构建好的 `List[ChatMessage]`，session 通过它读写对话历史。

## 文档索引

| 文档 | 说明 |
|------|------|
| [01-goals-duty.md](./01-goals-duty.md) | 设计目标与职责边界 |
| [02-architecture.md](./02-architecture.md) | 双轨模型、分层压缩、token 预算制的架构设计 |
| [03-data-model.md](./03-data-model.md) | SessionMemory、TokenCounter、Budget、Compressor 等核心抽象 |
| [04-dfd-interface.md](./04-dfd-interface.md) | 消息链构建流程、压缩触发时机、对外接口 |
| [05-test.md](./05-test.md) | 验证策略 |
