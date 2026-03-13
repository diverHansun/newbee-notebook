# Tools 模块设计文档

## 概述

Tools 模块（`core/tools/`）管理 AgentLoop 可调用的全部工具。本次重构包含两个核心变更：

1. **ToolRegistry + BuiltinToolProvider**：引入统一的工具注册中心，替代分散在各 Mode 中的工具构建逻辑。ToolRegistry 合并内置工具和 MCP 外部工具，是 ModeConfigFactory 获取工具列表的唯一入口。
2. **knowledge_base 统一检索工具**：将 HybridRetriever（pgvector + ES）封装为 runtime 可调用的统一工具，替代当前独立的 es_search_tool。
3. **统一工具协议**：显式定义 `ToolDefinition / ToolCallResult / SourceItem / ToolQualityMeta`，不再依赖 side-effect 收集来源。

## 文档索引

| 文档 | 说明 |
|------|------|
| [01-rag-tool-design.md](./01-rag-tool-design.md) | knowledge_base 工具设计：参数、内部流程、质量反馈、Source 提取 |
| [02-tool-registry.md](./02-tool-registry.md) | ToolRegistry 与 BuiltinToolProvider 设计：职责、接口、模式-工具映射、DI 集成 |
| [03-tool-contract.md](./03-tool-contract.md) | 统一工具协议：ToolDefinition、ToolCallResult、SourceItem、ToolQualityMeta |

## 重构后文件布局

```
core/tools/
    __init__.py
    registry.py              ToolRegistry：统一工具注册中心
    builtin_provider.py      BuiltinToolProvider：内置工具按模式分发
    knowledge_base.py        knowledge_base 工具（HybridRetriever: pgvector + ES）
    tavily_tools.py          Tavily Web 搜索工具（保持）
    zhipu_tools.py           Zhipu Web 搜索工具（保持）
    time.py                  时间工具（保持）
```

## 与其他模块的关系

| 模块 | 关系 |
|------|------|
| core/engine | ModeConfigFactory 通过 ToolRegistry 获取工具列表；AgentLoop 执行工具调用 |
| core/mcp | MCPClientManager 作为 MCP 工具来源，由 ToolRegistry 持有 |
| application/services | ChatService 注入 ToolRegistry，传递工具列表给 ModeConfigFactory |
| api/dependencies | ToolRegistry 作为应用级单例注入 |
