# MCP 模块：验证策略

## 1. 测试范围

| 测试对象 | 覆盖 |
|---------|------|
| 配置解析（JSON 读取、类型推断、环境变量展开） | 是 |
| 连接生命周期（懒加载、连接、断开、重连） | 是 |
| 工具发现与缓存 | 是 |
| 工具适配（MCP Tool -> ToolDefinition） | 是 |
| 工具调用路由（ToolDefinition.execute -> tools/call） | 是 |
| 动态开关（enable/disable Server） | 是 |
| 连接失败降级 | 是 |
| 状态查询接口 | 是 |

| 排除对象 | 理由 |
|---------|------|
| MCP Server 的具体工具逻辑 | 属于外部 Server 的职责 |
| AgentLoop 的工具调用循环 | 属于 engine 模块 |
| AppSettings 的持久化 | 属于 application/services 模块 |
| 前端 Settings Panel UI | 属于前端 |

## 2. 关键场景

### 2.1 配置解析

**场景：stdio 类型的配置解析**

输入包含 `command`、`args`、`env` 字段的 JSON。验证解析结果的 transport 为 "stdio"，各字段正确映射到 MCPServerConfig。

**场景：Streamable HTTP 类型的配置解析**

输入包含 `type: "streamable-http"`、`url`、`headers` 字段的 JSON。验证解析结果的 transport 为 "streamable-http"，url 和 headers 正确映射。

**场景：环境变量展开**

配置中包含 `${MY_VAR}` 和 `${MISSING:-fallback}`。设置 MY_VAR 环境变量后解析。验证 `${MY_VAR}` 被替换为环境变量值，`${MISSING:-fallback}` 被替换为 "fallback"。

**场景：环境变量缺失报错**

配置中包含 `${REQUIRED_VAR}`，未设置该环境变量。验证解析抛出明确错误。

**场景：配置文件不存在**

指定路径的文件不存在。验证返回空列表，不抛出异常。

**场景：多 Server 配置**

JSON 中包含 3 个 Server（2 个 stdio + 1 个 http）。验证返回 3 个 MCPServerConfig。

### 2.2 连接生命周期

**场景：懒加载首次连接**

MCPClientManager 创建后未调用 `get_tools()`。验证无连接建立。首次调用 `get_tools()`，验证触发连接和工具发现。

**场景：后续调用返回缓存**

首次 `get_tools()` 后，第二次调用。验证不重新连接，返回相同的工具列表。

**场景：应用退出关闭连接**

调用 `shutdown()`。验证所有 ClientSession 被关闭（stdio 子进程被终止）。

### 2.3 连接失败降级

**场景：单个 Server 连接失败**

配置 2 个 Server，mock 其中一个的 initialize 抛出异常。调用 `get_tools()`。验证：
- 失败的 Server 状态为 error，error_message 有值。
- 成功的 Server 工具正常返回。
- 不抛出异常。

**场景：所有 Server 连接失败**

配置 2 个 Server，mock 全部 initialize 失败。调用 `get_tools()`。验证返回空列表，不抛出异常。Agent 模式仍可使用内置工具。

**场景：Server 运行时断开**

Server 已连接成功后，mock ClientSession 的 call_tool 抛出连接异常。验证该 Server 状态切换为 error，下次 `get_tools()` 尝试重连。

### 2.4 工具适配

**场景：MCP 工具转为 ToolDefinition**

mock 一个 MCPToolInfo（name="get_weather", description="...", input_schema={...}）。调用 MCPToolAdapter.adapt()。验证返回的 ToolDefinition：
- name 为 `{server_name}_get_weather`。
- description 与原始描述一致。
- metadata 的参数 schema 与 input_schema 对应。

**场景：工具调用路由**

mock ClientSession.call_tool 返回包含 text content 的响应。通过适配后的 ToolDefinition 调用 execute(query="...")。验证 call_tool 被调用，参数正确传递，返回值为文本字符串。

**场景：MCP 响应包含多种内容类型**

mock call_tool 返回包含 text 和 image 两种类型的 content 数组。验证只提取 text 类型内容，image 被跳过。

**场景：工具调用返回错误**

mock call_tool 返回 isError=true 的响应。验证 ToolDefinition 返回错误信息字符串，不抛出异常（让 AgentLoop 的 LLM 知道工具失败后决策下一步）。

### 2.5 动态开关

**场景：禁用已连接的 Server**

Server 已连接成功，调用 `disable_server(name)`。验证：
- ClientSession 被关闭。
- `get_tools()` 返回的列表不再包含该 Server 的工具。
- `get_server_statuses()` 中该 Server 状态为 disconnected。

**场景：启用已禁用的 Server**

Server 处于禁用状态，调用 `enable_server(name)`。验证触发连接建立和工具发现，`get_tools()` 包含新启用 Server 的工具。

**场景：MCP 总开关关闭**

`mcp.enabled` 为 "false"。调用 `get_tools()`。验证返回空列表，不尝试连接任何 Server。

### 2.6 名称冲突

**场景：不同 Server 的同名工具**

两个 Server 各暴露一个名为 `search` 的工具。验证适配后的 ToolDefinition name 分别为 `server_a_search` 和 `server_b_search`，不冲突。

## 3. 集成测试

### 3.1 MCP 协议集成

使用 MCP Python SDK 的 FastMCP 创建一个测试用 MCP Server（stdio 传输），暴露一个简单工具（如 `echo`）。MCPClientManager 通过 stdio 连接该 Server。验证：
- 连接建立和握手成功。
- `tools/list` 正确返回工具描述。
- `tools/call` 正确执行并返回结果。
- `shutdown()` 正确终止子进程。

### 3.2 Agent 端到端

在 Agent 模式下发送请求，MCP 总开关打开，配置一个测试 MCP Server。验证：
- MCP 工具出现在 AgentLoop 的工具列表中。
- LLM 能够在需要时调用 MCP 工具。
- MCP 工具结果正确进入消息链。
- SSE 事件流中包含 MCP 工具的 ToolCallEvent 和 ToolResultEvent。

标记为慢测试。

### 3.3 Settings API 集成

通过 HTTP 客户端测试：
- `GET /api/v1/settings/mcp/servers` 返回 Server 列表和状态。
- `PUT /api/v1/settings` 设置 `mcp.enabled` 后，下次 Agent 请求的工具列表包含/不包含 MCP 工具。
- `PUT /api/v1/settings` 禁用单个 Server 后，`get_server_statuses()` 反映状态变化。

## 4. 验证方法

单元测试使用 pytest + pytest-asyncio。Mock MCP ClientSession 的 initialize、list_tools、call_tool 方法。Mock AppSettingsService 的 get/set 方法。

集成测试使用 MCP Python SDK 创建真实的 FastMCP Server 子进程。

测试文件：

```
tests/unit/core/mcp/
    test_config.py              配置解析、环境变量展开、类型推断
    test_client_manager.py      连接管理、懒加载、动态开关、降级
    test_tool_adapter.py        工具适配、调用路由、响应转换
tests/integration/core/mcp/
    test_mcp_protocol.py        MCP 协议集成（真实 Server 子进程）
tests/integration/api/
    test_mcp_settings.py        Settings API + MCP 状态查询
```

