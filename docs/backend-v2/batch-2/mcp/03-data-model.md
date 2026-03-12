# MCP 模块：核心概念与数据模型

## 1. MCPServerConfig

MCP Server 的静态配置，由 MCPConfigLoader 从 JSON 文件解析产出。

| 字段 | 含义 | 适用传输 |
|------|------|---------|
| name | Server 标识名（JSON 中的 key） | 通用 |
| transport | 传输类型 | 通用 |
| command | 可执行文件路径 | stdio |
| args | 命令行参数列表 | stdio |
| env | 环境变量字典 | stdio |
| url | Server 端点 URL | http |
| headers | HTTP 请求头字典 | http |

transport 取值：
- `"stdio"`：有 `command` 字段时隐式推断为 stdio（与 Claude Code 行为一致）。
- `"http"`：`type` 字段显式指定为 `"http"`。

### 1.1 配置文件格式

```json
{
  "mcpServers": {
    "local-tool": {
      "command": "python",
      "args": ["-m", "my_tool_server"],
      "env": {
        "API_KEY": "${MY_API_KEY}"
      }
    },
    "remote-service": {
      "type": "http",
      "url": "https://api.example.com/mcp",
      "headers": {
        "Authorization": "Bearer ${SERVICE_TOKEN}"
      }
    }
  }
}
```

类型推断规则：存在 `command` 字段 -> stdio；存在 `type: "http"` -> http。两者都存在时以 `type` 为准。

### 1.2 环境变量展开

配置文件中的 `command`、`args`、`env`、`url`、`headers` 字段均支持 `${VAR}` 和 `${VAR:-default}` 语法。

展开规则：
- `${VAR}`：从系统环境变量读取，变量未设置时解析报错。
- `${VAR:-default}`：变量未设置时使用 default 值。
- 展开发生在配置解析阶段，展开后的值不再包含 `${}` 标记。

## 2. MCPServerStatus

单个 MCP Server 的运行时状态。

| 字段 | 含义 |
|------|------|
| name | Server 标识名 |
| transport | 传输类型（"stdio" / "http"） |
| enabled | 是否启用（来自 AppSettings） |
| connection_status | 连接状态 |
| tool_count | 该 Server 提供的工具数量（未连接时为 0） |
| error_message | 连接失败时的错误信息 |

connection_status 取值：

| 状态 | 含义 |
|------|------|
| disconnected | 未连接（初始状态，或已断开） |
| connecting | 正在建立连接和协议握手 |
| connected | 连接正常，工具已发现 |
| error | 连接失败或运行时错误 |

### 2.1 状态流转

```
disconnected
    |
    | (首次 Agent 请求 / enable_server)
    v
connecting
    |
    +---(握手成功)--> connected
    |
    +---(握手失败)--> error
                        |
                        | (重试 / 下次 Agent 请求)
                        v
                    connecting

connected
    |
    +---(disable_server)--> disconnected
    |
    +---(Server 进程退出 / 网络断开)--> error
    |
    +---(tools/list_changed 通知)--> connected (刷新工具列表)
```

## 3. MCPToolInfo

MCP Server 暴露的单个工具的描述信息，缓存在 MCPClientManager 中。

| 字段 | 含义 |
|------|------|
| server_name | 所属 Server 标识名 |
| name | 工具原始名称（MCP Server 定义的） |
| qualified_name | 全限定名（`{server_name}__{name}`），用于避免名称冲突 |
| description | 工具描述，注入 Agent 的工具描述中 |
| input_schema | 工具参数的 JSON Schema |

qualified_name 示例：Server 名为 `weather`，工具名为 `get_forecast`，则全限定名为 `weather__get_forecast`。

## 4. AppSettings 键定义

MCP 相关的开关状态存储在 AppSettings 键值表中。

| 键 | 值类型 | 含义 | 默认值 |
|----|--------|------|--------|
| `mcp.enabled` | string ("true"/"false") | MCP 总开关 | "false" |
| `mcp.servers.{name}.enabled` | string ("true"/"false") | 单个 Server 启用开关 | "true" |

逻辑：`mcp.enabled` 为 "false" 时，忽略所有 Server 的个体开关，不连接任何 Server，不注入任何 MCP 工具。`mcp.enabled` 为 "true" 时，仅连接个体开关也为 "true" 的 Server。

单个 Server 的默认启用状态为 "true"。即配置文件中新增一个 Server 后，只要 MCP 总开关打开，该 Server 默认启用。用户可以在 Settings Panel 中手动禁用。

## 5. 生命周期

### 5.1 MCPServerConfig

应用启动或配置文件变更时解析生成。配置文件不变则不会重新解析。属于静态配置数据。

### 5.2 MCPClientManager

应用级单例。首次 `get_tools()` 调用时初始化连接。应用退出时调用 `shutdown()` 关闭所有连接和子进程。

### 5.3 ClientSession（MCP SDK）

每个已连接的 Server 对应一个 ClientSession 实例。stdio 类型的 ClientSession 关联一个子进程。HTTP 类型的 ClientSession 关联一个 HTTP 会话。连接保持复用，直到 Server 被禁用、连接异常、或应用退出。

### 5.4 MCPToolInfo

连接建立后通过 `tools/list` 获取并缓存。`tools/list_changed` 通知到达时刷新。Server 断开后清除。

### 5.5 BaseTool（适配后）

由 MCPToolAdapter 在 `get_tools()` 时基于 MCPToolInfo 创建。每次 `get_tools()` 调用返回当前有效的工具列表。工具实例本身是轻量的——实际调用通过 ClientSession 路由。
