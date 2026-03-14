# MCP 模块：数据流与接口定义

## 1. 上下文与范围

MCP 模块位于 ToolRegistry 与外部 MCP Server 之间：

- 上游：ToolRegistry 持有 MCPClientManager，在 Agent 模式下调用 `get_tools()` 获取 MCP 工具，与内置工具合并。
- 下游：外部 MCP Server（本地子进程或远程 HTTP 服务）。
- 同层：core/tools 的 BuiltinToolProvider 提供内置工具，MCPClientManager 提供外部工具，两者在 ToolRegistry 中合并。
- 控制面：AppSettings 存储开关状态，Settings Panel API 读写开关。

## 2. 端到端数据流

### 2.1 Agent 请求主流程（MCP 工具参与）

1. 用户在 Agent 模式发送消息。
2. ChatService 检查 AppSettings 中 `mcp.enabled` 是否为 "true"。
3. ChatService 调用 `ToolRegistry.get_tools(mode=AGENT, mcp_enabled=True)`。
4. ToolRegistry 内部：
   - 调用 `BuiltinToolProvider.get_tools(AGENT)` 获取内置工具。
   - 调用 `MCPClientManager.get_tools()` 获取 MCP 工具（首次调用触发懒加载连接）。
   - 合并两个列表返回。
5. ChatService 将工具列表传入 `ModeConfigFactory.build(tools, allowed_document_ids, ...)`。
6. ModeConfigFactory 绑定 allowed_document_ids 到 RAG/ES 工具，产出 ModeConfig。
7. AgentLoop 使用完整工具列表执行。
8. LLM 决定调用某个 MCP 工具（如 `weather_get_forecast`）。
9. MCPToolAdapter 的 ToolDefinition 包装器接收调用，通过 MCPClientManager 找到对应的 ClientSession。
10. ClientSession 发送 `tools/call` JSON-RPC 请求到 MCP Server。
11. MCP Server 执行工具，返回结果。
12. MCPToolAdapter 将 MCP 响应（content 数组）转换为字符串，返回给 AgentLoop。
13. AgentLoop 将工具结果追加到消息链，继续循环。

### 2.2 懒加载连接流程

```
MCPClientManager.get_tools()
    |
    +--> 已初始化？ --> 是 --> 返回缓存的工具列表
    |
    +--> 否 --> MCPConfigLoader.load() 读取配置文件
                    |
                    v
                遍历启用的 Server
                    |
                    v
                每个 Server：
                    |
                    +--> stdio: 启动子进程，建立 stdin/stdout 通道
                    |    ClientSession(StdioTransport(...))
                    |
                    +--> streamable-http: 建立 HTTP 会话
                    |    ClientSession(streamablehttp_client(url, headers))
                    |
                    v
                session.initialize()  协议握手
                    |
                    v
                session.list_tools()  工具发现
                    |
                    v
                缓存 MCPToolInfo 列表
                    |
                    +--(连接失败)--> 记录错误，跳过该 Server
                    |
                    v
                返回所有成功连接 Server 的工具列表
```

### 2.3 前端开关操作流程

**MCP 总开关切换**

```
前端 PUT /api/v1/settings {"key": "mcp.enabled", "value": "true"}
    |
    v
AppSettingsService.set("mcp.enabled", "true")
    |
    v
（下一次 Agent 请求时，MCPClientManager 检查开关状态，触发连接）
```

**单个 Server 启用/禁用**

```
前端 PUT /api/v1/settings {"key": "mcp.servers.weather.enabled", "value": "false"}
    |
    v
AppSettingsService.set("mcp.servers.weather.enabled", "false")
    |
    v
MCPClientManager.disable_server("weather")
    |
    v
关闭 weather 的 ClientSession（stdio: 终止子进程，http: 关闭会话）
    |
    v
从工具列表缓存中移除 weather 的工具
```

### 2.4 配置文件重新加载

配置文件变更后需要应用重启或提供手动刷新机制。当前设计选择不做热加载，原因：

- 配置文件变更是低频操作（新增/删除 MCP Server）。
- 热加载需要 file watcher 或定期轮询，增加复杂度。
- 应用重启代价低（开发环境 uvicorn reload，生产环境容器重启）。

后续版本可考虑增加 `POST /api/v1/settings/mcp/reload` 手动刷新端点。

## 3. 接口定义

### 3.1 MCPConfigLoader

```python
class MCPConfigLoader:
    @staticmethod
    def load(config_path: Path) -> List[MCPServerConfig]:
        """读取 JSON 配置文件，解析为 MCPServerConfig 列表。

        执行环境变量展开。验证必填字段。
        配置文件不存在时返回空列表（MCP 功能静默禁用）。
        """
        ...
```

### 3.2 MCPClientManager

```python
class MCPClientManager:
    def __init__(self, config_path: Path) -> None:
        """初始化管理器。不立即连接任何 Server。"""
        ...

    async def get_tools(self) -> List[ToolDefinition]:
        """返回所有已启用且已连接 Server 的工具列表。

        首次调用触发懒加载：读取配置、连接 Server、发现工具。
        后续调用返回缓存。
        MCP 总开关关闭时返回空列表。
        """
        ...

    async def enable_server(self, name: str) -> None:
        """启用指定 Server。触发连接建立和工具发现。"""
        ...

    async def disable_server(self, name: str) -> None:
        """禁用指定 Server。断开连接，移除其工具。"""
        ...

    async def get_server_statuses(self) -> List[MCPServerStatus]:
        """返回所有配置中的 Server 状态列表。

        不触发连接。未连接的 Server 状态为 disconnected。
        """
        ...

    async def shutdown(self) -> None:
        """关闭所有连接和子进程。应用退出时调用。"""
        ...
```

### 3.3 MCPToolAdapter

```python
class MCPToolAdapter:
    @staticmethod
    def adapt(
        tool_info: MCPToolInfo,
        client_session: ClientSession,
    ) -> ToolDefinition:
        """将单个 MCP 工具描述适配为 ToolDefinition。

        返回的 ToolDefinition:
        - name: tool_info.qualified_name
        - description: tool_info.description
        - fn_schema: 从 tool_info.input_schema 生成
        - execute: 通过 client_session.call_tool() 执行
        """
        ...

    @staticmethod
    def convert_response(mcp_result) -> str:
        """将 MCP tools/call 响应转换为字符串。

        MCP 响应的 content 是数组，可包含 text、image、resource 等类型。
        当前只提取 text 类型的内容拼接为字符串。
        image 类型记录日志但不传递（AgentLoop 消息链暂不支持图片）。
        """
        ...
```

### 3.4 Settings API

MCP 相关的前端交互通过现有的 AppSettings API 完成，不新增专用端点。

**获取 MCP Server 列表及状态**

新增一个只读端点：

```
GET /api/v1/settings/mcp/servers
```

响应：

```json
{
  "mcp_enabled": true,
  "servers": [
    {
      "name": "weather",
      "transport": "http",
      "enabled": true,
      "connection_status": "connected",
      "tool_count": 3,
      "error_message": null
    },
    {
      "name": "local-db",
      "transport": "stdio",
      "enabled": false,
      "connection_status": "disconnected",
      "tool_count": 0,
      "error_message": null
    }
  ]
}
```

**MCP 总开关**

```
PUT /api/v1/settings
{"key": "mcp.enabled", "value": "true"}
```

**单个 Server 开关**

```
PUT /api/v1/settings
{"key": "mcp.servers.weather.enabled", "value": "false"}
```

使用现有的 AppSettings PUT 端点，无需新增。

### 3.5 DI 集成

MCPClientManager 不再直接注入 ChatService。它作为 ToolRegistry 的组成部分，通过 ToolRegistry 单例间接使用：

```python
# api/dependencies.py

_mcp_client_manager: Optional[MCPClientManager] = None

async def get_mcp_client_manager(
    settings_service: AppSettingsService = Depends(get_app_settings_service),
) -> MCPClientManager:
    global _mcp_client_manager
    if _mcp_client_manager is None:
        config_path = get_configs_directory() / "mcp.json"
        _mcp_client_manager = MCPClientManager(config_path, settings_service)
    return _mcp_client_manager

# MCPClientManager 注入 ToolRegistry，不直接注入 ChatService
async def get_tool_registry() -> ToolRegistry:
    ...
    mcp_manager = await get_mcp_client_manager()
    builtin = BuiltinToolProvider(pg_index, es_index)
    return ToolRegistry(builtin, mcp_manager)

# ChatService 注入 ToolRegistry
async def get_chat_service(
    ...,
    tool_registry: ToolRegistry = Depends(get_tool_registry),
) -> ChatService:
    return ChatService(..., tool_registry=tool_registry)
```

### 3.6 ToolRegistry 集成

MCP 工具的合并不再由 ModeConfigFactory 或 ChatService 手动处理。ToolRegistry 统一管理：

```python
# ToolRegistry.get_tools() 内部逻辑

tools = self._builtin.get_tools(mode)              # 内置工具
if mode == ModeType.AGENT and mcp_enabled:
    mcp_tools = await self._mcp.get_tools()         # MCP 工具
    tools.extend(mcp_tools)
return tools
```

ChatService 只需调用 `ToolRegistry.get_tools(mode, mcp_enabled)`，不直接与 MCPClientManager 交互。ModeConfigFactory 接收已合并的工具列表，只负责绑定 allowed_document_ids 等请求级参数。

## 4. 数据所有权

| 数据 | 所有者 | MCP 模块的角色 |
|------|--------|---------------|
| configs/mcp.json 配置文件 | 用户/文件系统 | 消费者（只读） |
| AppSettings 开关状态 | AppSettingsService | 消费者（读取开关） |
| MCPServerConfig | MCPConfigLoader | 生产者 |
| ClientSession 连接 | MCPClientManager | 所有者（创建、维护、销毁） |
| MCPToolInfo 缓存 | MCPClientManager | 所有者（缓存、刷新） |
| ToolDefinition（适配后） | MCPToolAdapter | 生产者（创建后交给 ToolRegistry） |
| 工具调用结果 | MCP Server | MCP 模块是中转者（协议转换后传递给 AgentLoop） |

