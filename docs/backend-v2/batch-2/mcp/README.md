# MCP 模块设计文档

## 概述

MCP（Model Context Protocol）模块为 Agent 模式提供外部工具扩展能力。它作为 MCP Client，连接外部 MCP Server，将 Server 暴露的工具转换为 AgentLoop 可调用的标准工具，与内置工具（knowledge_base、web_search、time）并列使用。

仅 Agent 模式接入 MCP 工具。Ask、Explain、Conclude 模式不涉及。

## 文档索引

| 文档 | 说明 |
|------|------|
| [01-goals-duty.md](./01-goals-duty.md) | 设计目标与职责边界 |
| [02-architecture.md](./02-architecture.md) | 配置层、Client 管理器、工具适配器架构 |
| [03-data-model.md](./03-data-model.md) | 核心概念与数据模型：MCPServerConfig、连接状态、工具描述 |
| [04-dfd-interface.md](./04-dfd-interface.md) | 数据流、接口定义、前端交互协议 |
| [05-test.md](./05-test.md) | 验证策略 |

## 设计决策

| 决策 | 结论 | 依据 |
|------|------|------|
| MCP 适用范围 | 仅 Agent 模式 | Ask/Explain/Conclude 的工具集合固定（RAG 为主），不需要外部扩展 |
| 传输方式 | stdio + HTTP streamable 混合 | stdio 适合本地轻量工具，HTTP 适合远程服务；MCP 协议原生支持两种 |
| 配置格式 | JSON 文件，对齐 Claude Code | 降低用户认知成本，复用社区已有的 MCP Server 配置 |
| 前端控制 | Settings Panel 中 MCP 总开关 + 单个 Server 开关 | 配置变更引导用户编辑 JSON 文件，避免前端处理复杂字段 |
| 连接生命周期 | 懒加载，首次 Agent 请求触发 | 避免启动时连接失败阻塞应用；与 pgvector/ES 的单例懒加载模式一致 |
| 工具注入方式 | 工具描述随内置工具一起注入 Agent | LLM 自主决策是否调用，不做额外意图检测 |
| 作用域 | 全局，所有 notebook 共享 | 与 Settings Panel 的全局设置架构一致 |

## 与其他模块的关系

| 模块 | 关系 |
|------|------|
| core/tools (ToolRegistry) | MCPClientManager 作为 ToolRegistry 的 MCP 工具来源，ToolRegistry 合并内置工具 + MCP 工具 |
| core/tools (BuiltinToolProvider) | 内置工具与 MCP 工具并列，共享 BaseTool 接口，在 ToolRegistry 中合并 |
| core/engine | ModeConfigFactory 接收 ToolRegistry 已合并的工具列表，AgentLoop 透明调用 |
| application/services | ChatService 注入 ToolRegistry（内含 MCPClientManager），不直接与 MCPClientManager 交互 |
| api/dependencies | MCPClientManager 作为应用级单例注入 ToolRegistry |
| AppSettings | 存储 MCP 总开关和单个 Server 启用/禁用状态 |
