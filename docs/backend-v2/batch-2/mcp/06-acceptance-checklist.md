# MCP 模块：API / 文档验收清单

## 1. 验收范围

本清单用于 batch-2 MCP 阶段的真实联调验收，目标是确认：

- 配置文件路径固定为仓库级 `configs/mcp.json`
- 配置格式遵循 Anthropic / MCP 社区常用 `mcpServers` JSON 结构
- 仅支持 `stdio` 与 `streamable-http`
- MCP 工具只注入 `agent`
- Settings API、前端 MCP 面板、真实 MCP Server 连接状态保持一致
- 真实 MCP 工具能够被 agent 模式调用并返回可用结果

## 2. 真实配置基线

### 2.1 配置文件位置

```text
configs/mcp.json
```

说明：

- `newbee_notebook/configs` 只存包内后端默认配置
- MCP 运行时配置使用仓库级 `configs/mcp.json`
- 密钥不直接写入 JSON，统一通过 `${VAR}` / `${VAR:-default}` 占位展开

### 2.2 Firecrawl 配置示例

以下配置与 Firecrawl 官方 MCP Server 仓库提供的 `npx -y firecrawl-mcp` 用法对齐，并适配本项目当前的 `configs/mcp.json` 读取器：

```json
{
  "mcpServers": {
    "firecrawl": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": {
        "FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}"
      }
    }
  }
}
```

要求：

- `FIRECRAWL_API_KEY` 由 `.env` 提供
- `configs/mcp.json` 允许 UTF-8 BOM
- server 名称建议简洁稳定，工具会被命名为 `firecrawl_<tool_name>`

## 3. API 验收清单

### 3.1 状态查询

接口：

```text
GET /api/v1/settings/mcp/servers
```

验收点：

- 返回 `mcp_enabled`
- 返回 `servers[]`
- 每个 server 包含：
  - `name`
  - `transport`
  - `enabled`
  - `connection_status`
  - `tool_count`
  - `error_message`
- 使用真实 Firecrawl 配置时，应看到：
  - `name = firecrawl`
  - `transport = stdio`
  - `connection_status = connected`
  - `tool_count > 0`

### 3.2 总开关

接口：

```text
PUT /api/v1/settings
{"key":"mcp.enabled","value":"false"}
```

验收点：

- 调用后立即断开所有 MCP 连接
- `GET /api/v1/settings/mcp/servers` 返回：
  - `mcp_enabled = false`
  - server `enabled = false`
  - `connection_status = disconnected`
  - `tool_count = 0`

### 3.3 单服务开关

接口：

```text
PUT /api/v1/settings
{"key":"mcp.servers.firecrawl.enabled","value":"false"}
```

验收点：

- 全局 MCP 仍为开启时，单服务关闭后立即断连
- 仅 firecrawl 服务器状态改变，不影响其它 server
- 重新开启后可恢复连接和工具发现

## 4. 前端验收清单

页面：

```text
全局控制面板 -> MCP
```

验收点：

- 显示配置文件路径 `configs/mcp.json`
- 展示 `firecrawl` server 条目
- 展示 transport `stdio`
- 展示连接状态与工具数量
- 全局开关与单服务开关的 UI 状态和后端接口一致
- 前端通过 `/api/v1/settings/mcp/servers` 代理访问时返回 `200`

## 5. Agent 真实工具调用验收

模式范围：

- `agent`：允许 MCP 工具
- `ask / explain / conclude`：不注入 MCP 工具

验收示例：

- 新建一个空 notebook
- 发送 agent 请求，明确要求使用 `firecrawl_search` 检索 Firecrawl 官网
- 观察 SSE 事件流，至少包含：
  - `tool_call`
  - `tool_result`
  - `content`

通过标准：

- `tool_call.tool_name = firecrawl_firecrawl_search`
- `tool_result.success = true`
- 最终回答包含官网标题与 URL

## 6. 本轮真实联调结果

基于 `configs/mcp.json` 的 Firecrawl 真实配置，已完成以下联调：

- 后端直连：
  - `GET /api/v1/settings/mcp/servers` -> `200`
  - `firecrawl / stdio / connected / tool_count=12`
- 前端代理：
  - `GET /api/v1/settings/mcp/servers` -> `200`
- 前端面板：
  - MCP tab 正确显示 `firecrawl`
  - 全局关闭后即时断连
  - 单服务关闭后即时断连
  - 重新开启后恢复连接
- agent 真实调用：
  - 成功调用 `firecrawl_firecrawl_search`
  - 返回 `Firecrawl - The Web Data API for AI`
  - 返回 URL `https://www.firecrawl.dev/`

## 7. 结论

当前 batch-2 MCP 阶段的配置、API、前端面板、真实 Firecrawl Server 集成已形成闭环，可作为后续合并到 `backend-v2` 前的验收基线。
