# MCP 模块：架构设计

## 1. 架构总览

MCP 模块由四个组件构成：

- **MCPConfigLoader**：配置文件解析，产出结构化的 Server 配置列表。
- **MCPClientManager**：连接池管理器，维护所有 MCP Client 的生命周期。
- **MCPToolAdapter**：工具适配层，将 MCP 工具转为 `ToolDefinition`。
- **types**：数据类型定义。

```
mcp.json                    配置文件（用户编辑）
    |
    v
MCPConfigLoader             JSON --> MCPServerConfig 列表
    |
    v
MCPClientManager            MCPServerConfig --> ClientSession 连接池
    |                       懒加载 + 长连接复用
    v
MCPToolAdapter              MCP Tool Schema --> ToolDefinition 列表
    |
    v
ToolRegistry                合并 BuiltinToolProvider + MCPClientManager
    |                       按 mode + mcp_enabled 返回工具列表
    v
ModeConfigFactory           绑定 allowed_doc_ids --> AgentLoop
```

### 1.1 与当前工具系统的对比

| 维度 | 当前内置工具 | MCP 工具 |
|------|-------------|----------|
| 注册方式 | BuiltinToolProvider 环境变量驱动 | 配置文件声明，运行时发现 |
| 实现位置 | core/tools/ 本地 Python 函数 | 外部 MCP Server 进程/服务 |
| 调用方式 | 直接函数调用 | MCP 协议 JSON-RPC（tools/call） |
| 对 runtime | ToolDefinition 接口 | 适配为统一工具协议（透明） |
| 可用模式 | 按模式配置（Agent/Ask/Explain/Conclude） | 仅 Agent 模式 |

## 2. 设计模式与理由

### 2.1 单例管理器 + 懒加载

MCPClientManager 是应用级单例，与 `get_pg_index_singleton()` 管理模式一致。

理由：
- MCP 连接建立需要协议握手（initialize + capability 协商），开销不可忽略。每请求新建不现实。
- stdio 类型的 Server 是子进程，频繁创建销毁浪费系统资源。
- 懒加载避免应用启动时因 MCP Server 不可用而阻塞。首次 Agent 请求触发连接，之后复用。

### 2.2 配置文件作为唯一数据源

MCP Server 的定义（command、args、env、url、headers）全部来自 JSON 配置文件。AppSettings 数据库只存储开关状态（`mcp.enabled`、`mcp.servers.{name}.enabled`），不存储 Server 定义。

理由：
- Server 配置涉及命令路径、环境变量、认证令牌等敏感信息，文件系统比数据库更安全和可控。
- 与 Claude Code 的 `.mcp.json` 格式对齐，用户可以直接复制社区配置。
- 前端不需要处理复杂的配置表单字段。

### 2.3 适配器模式

MCPToolAdapter 将 MCP 工具描述适配为 runtime 的 `ToolDefinition` 接口。这是经典的适配器模式。

理由：
- runtime 只认识 `ToolDefinition` 协议（schema + execute）。
- MCP 工具的调用走 JSON-RPC 协议（tools/call），返回格式与本地函数不同。
- 适配层封装协议差异，对 AgentLoop 完全透明。

### 2.4 连接失败静默降级

单个 MCP Server 连接失败时，记录错误日志，跳过该 Server，其余 Server 和内置工具正常使用。

理由：
- 外部 Server 的可用性不在系统控制范围内。一个 Server 不可用不应阻塞整个 Agent 功能。
- 前端 Settings Panel 展示连接状态，用户可以看到哪个 Server 有问题。
- 与 MCP 协议的设计理念一致——Host 管理多个独立的 Client/Server 连接。

### 2.5 环境变量展开

配置文件中的 `${VAR}` 和 `${VAR:-default}` 在配置解析阶段展开，与 Claude Code 行为一致。

理由：
- 敏感信息（API Key、Token）不应硬编码在配置文件中。
- 环境变量展开让同一份配置文件可以在不同环境（开发/生产）中使用。

## 3. 模块结构与文件布局

```
core/mcp/
    __init__.py
    config.py              MCPConfigLoader：配置解析与环境变量展开
    client_manager.py      MCPClientManager：连接池管理、懒加载、动态开关
    tool_adapter.py        MCPToolAdapter：MCP 工具 --> ToolDefinition 适配
    types.py               数据类型：MCPServerConfig、MCPServerStatus、MCPToolInfo
```

### 3.1 文件职责

**config.py** -- 配置解析

MCPConfigLoader 读取 JSON 配置文件，解析为 `List[MCPServerConfig]`。处理两种传输类型的字段差异（stdio: command/args/env，HTTP: url/headers）。执行 `${VAR:-default}` 环境变量展开。验证必填字段。

**client_manager.py** -- 连接池管理

MCPClientManager 维护 `Dict[str, ClientSession]` 连接池。核心方法：
- `get_tools()` -- 返回所有已启用且已连接的 Server 的工具列表（触发懒加载）
- `enable_server(name)` / `disable_server(name)` -- 动态开关
- `get_server_statuses()` -- 返回所有 Server 的连接状态
- `shutdown()` -- 关闭所有连接（应用退出时）

**tool_adapter.py** -- 工具适配

MCPToolAdapter 将 MCP 的工具描述（name, description, inputSchema）转换为 `ToolDefinition`。工具调用时，通过对应的 ClientSession 执行 `tools/call`，将 MCP 响应转换为 `ToolCallResult` 返回给 runtime。

**types.py** -- 数据类型

纯数据类，无逻辑。定义 MCPServerConfig、MCPServerStatus、MCPToolInfo 等结构。

## 4. 架构约束与权衡

### 4.1 MCP Python SDK 依赖

MCPClientManager 依赖 `mcp` Python SDK（`mcp.client.session.ClientSession`）进行协议通信。需要在 `pyproject.toml` 中新增 `mcp` 依赖。

SDK 提供 stdio 和 HTTP 两种传输的 Client 实现。如果 SDK 版本不兼容或有 bug，需要 pin 版本或 patch。

### 4.2 stdio Server 的进程管理

stdio 类型的 MCP Server 作为子进程运行。需要注意：
- 子进程异常退出时的检测和重连。
- 应用退出时确保子进程被正确终止（shutdown 钩子）。
- Windows 环境下 `npx` 等命令可能需要 `cmd /c` 包装。

### 4.3 工具名称冲突

不同 MCP Server 可能暴露同名工具，或 MCP 工具名与内置工具名冲突。解决策略：为 MCP 工具添加 Server 名前缀（`{server_name}__{tool_name}`），确保全局唯一。

### 4.4 工具调用延迟

MCP 工具调用经过 JSON-RPC 序列化、网络传输（HTTP）或进程间通信（stdio），延迟高于本地函数调用。对于延迟敏感的场景，用户应优先使用内置工具。

### 4.5 MCP 工具无 Source 产出

当前内置的 knowledge_base 工具返回结构化的 SourceItem。MCP 工具的返回值是自由格式的文本/图片/资源，不包含 SourceItem 结构。MCP 工具调用不会产出 SourceEvent。如果后续需要 MCP 工具提供来源引用，需要定义扩展协议。
