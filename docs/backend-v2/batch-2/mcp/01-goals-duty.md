# MCP 模块：设计目标与职责边界

## 1. 设计目标

### 1.1 可插拔的外部工具扩展

Agent 模式的工具集合从"编译时固定"变为"运行时可扩展"。用户通过配置文件声明 MCP Server，系统自动发现 Server 提供的工具并注入 Agent 的工具列表。新增外部工具不需要修改后端代码。

### 1.2 对齐 Claude Code 配置协议

MCP Server 的配置格式与 Claude Code 的 `.mcp.json` 完全对齐。用户可以直接复用社区已有的 MCP Server 配置，降低接入成本。配置文件使用 JSON 格式，支持 stdio 和 HTTP streamable 两种传输方式。

### 1.3 对 AgentLoop 透明

MCP 工具经过适配后与内置工具（knowledge_base、web_search、time）共享同一接口（BaseTool）。AgentLoop 不区分工具来源，LLM 根据工具描述自主决策是否调用。MCP 模块的存在与否不影响 AgentLoop 的执行逻辑。

### 1.4 前端简洁控制

前端 Settings Panel 提供两级开关：MCP 总开关和单个 Server 的启用/禁用开关。不在前端暴露配置编辑能力，配置变更引导用户直接编辑 JSON 文件。

### 1.5 连接容错

单个 MCP Server 连接失败不影响系统整体运行。Agent 模式在缺少某个 MCP Server 时，仍然可以使用内置工具和其他正常连接的 MCP Server。

## 2. 职责

### 2.1 配置解析

读取 MCP Server 配置文件（JSON），解析 stdio 和 HTTP 两种传输类型的配置参数。支持环境变量展开（`${VAR}` 和 `${VAR:-default}` 语法）。结合 AppSettings 中的开关状态，确定哪些 Server 当前处于启用状态。

### 2.2 连接生命周期管理

管理 MCP Client 与 Server 之间的连接。对 stdio 类型，管理子进程的启动和终止。对 HTTP 类型，管理 HTTP 会话的建立和关闭。连接采用懒加载策略——首次 Agent 请求触发连接建立，之后保持复用。

执行 MCP 协议的初始化握手（initialize -> initialized），完成 capability 协商。

### 2.3 工具发现

连接建立后，调用 MCP 协议的 `tools/list` 获取 Server 暴露的工具列表。缓存工具描述（name、description、inputSchema）。监听 `notifications/tools/list_changed` 通知，动态刷新工具列表。

### 2.4 工具适配

将 MCP 工具描述转换为 AgentLoop 可用的 BaseTool 实例。适配内容包括：
- name 和 description 直接映射
- inputSchema（JSON Schema）转换为工具的参数定义
- 工具调用时，将参数通过 MCP 协议的 `tools/call` 路由到对应的 Server
- 工具返回值从 MCP 响应格式转换为 AgentLoop 期望的字符串格式

### 2.5 动态开关响应

响应前端的 Server 启用/禁用操作。启用时触发连接建立和工具发现；禁用时断开连接，从工具列表中移除该 Server 的工具。

### 2.6 状态查询

提供 MCP Server 列表及其连接状态的查询接口，供前端 Settings Panel 展示。

## 3. 非职责

### 3.1 MCP Server 实现

MCP 模块只实现 Client 端。不实现任何 MCP Server。外部 MCP Server 由用户自行部署和管理。

### 3.2 内置工具管理

knowledge_base、web_search、time 等内置工具的注册和管理仍由 core/tools 模块负责。MCP 模块不干预内置工具的构建逻辑。

### 3.3 非 Agent 模式的工具注入

Ask、Explain、Conclude 模式的工具集合由 ModeConfigFactory 根据模式类型固定配置，不接入 MCP 工具。

### 3.4 配置文件的 CRUD UI

前端不提供 MCP Server 配置的新增、编辑、删除界面。配置变更由用户直接编辑 JSON 文件完成。前端仅提供开关控制和状态展示。

### 3.5 MCP Resources 和 Prompts

当前版本仅接入 MCP 的 Tools 能力。MCP 协议中的 Resources（只读数据源）和 Prompts（可复用提示模板）不在本次设计范围内。后续版本可按需扩展。

### 3.6 MCP Sampling

MCP 协议允许 Server 通过 Client 请求 LLM 补全（sampling/createMessage）。当前版本不支持此能力。MCP Server 不能通过我们的系统调用 LLM。
