# 第二批：AI 能力升级层

本批次包含 4 个模块。Agent 重构是核心，Skill 和 MCP 依赖 Agent 重构完成后接入，图片接口依赖 MinIO 完成后存储图片。

---

## 模块 1: Agent 模式重构

### 目标

将现有 chat 模式升级为 Agent 模式。Agent 作为通用执行者，整合工具调用、RAG 检索、Skill 和 MCP 能力。同时保留 ask 模式作为专注文档知识解读的独立通道。

### 模式定位重新定义

| 模式 | 角色定位 | Agent 引擎 | 核心能力 |
|------|---------|-----------|---------|
| Agent | 通用执行者 | FunctionAgent | MCP/Skill 执行为主，RAG/ES/Web 搜索作为可选工具 |
| Ask | 文档知识专家 | ReActAgent | HybridRetriever 为核心，文档内容深度 Q&A 与推理 |
| Explain | 选中文本解释 | QueryEngine | 保持现有 CondensePlusContext 实现 |
| Conclude | 选中文本总结 | QueryEngine | 保持现有 CondensePlusContext 实现 |

### 职责

- ChatMode 重命名为 AgentMode，扩展工具注册机制
- ModeType 枚举从 `chat` 改为 `agent`
- Agent 的工具集统一管理：内置工具 + Skill 工具 + MCP 工具
- RAG 能力包装为 FunctionTool，Agent 自主判断是否需要检索
- API 端点调整 (`/chat` 保留为兼容别名)

### 非职责

- 不修改 Ask 模式的 ReActAgent 和 HybridRetriever 实现
- 不修改 Explain/Conclude 的 QueryEngine 实现
- 不改动内存管理策略 (Agent/Ask 共享 `_memory`，Explain/Conclude 共享 `_ec_memory`)

### 与 Ask 模式的区别

- Agent 模式的 RAG 是工具之一，Agent 自主决定何时使用
- Ask 模式的 RAG 是核心流程，每次请求必定执行文档检索
- Agent 适合开放性问题和任务执行
- Ask 适合针对文档内容的精确问答

### 涉及文件

- `core/engine/modes/chat_mode.py` -> 重命名/扩展为 `agent_mode.py`
- `core/engine/selector.py` -> 适配新模式名称
- `core/tools/tool_registry.py` -> 扩展动态注册接口
- `domain/value_objects/mode_type.py` -> 枚举变更
- `api/routers/chat.py` -> 端点调整

---

## 模块 2: Skill 系统

### 目标

实现 Skill 机制，为 Agent 提供预定义的任务流能力。参考 Anthropic Skills 的设计理念，在后端 Python/LlamaIndex 生态中自行适配。

### 概念定义

Skill 是预定义的 "prompt + tool 组合"，当 Agent 遇到特定场景时可调用对应 Skill 获得更好的表现。每个 Skill 封装了专用的系统指令、所需工具和输出格式。

### 职责

- 定义 Skill 的数据结构和配置格式 (YAML)
- 实现 Skill 加载和注册机制
- 将 Skill 作为 FunctionTool 注册到 Agent 的工具集
- 提供内置 Skill (文档摘要、文档对比、术语提取等)
- 支持用户通过 YAML 文件自定义 Skill

### 非职责

- 不实现 Anthropic Skills 协议本身 (仅参考其理念)
- 不涉及前端 Skill 管理界面 (通过配置文件管理)

### 配置位置

`configs/skills/*.yaml`，每个文件定义一个或一组 Skill。

### 依赖

依赖 Agent 模式重构完成，Skill 工具注册到 AgentMode 的工具集中。

### 待补充的详细设计

详见 `docs/backend-v2/skills/` (后续逐步完善)

---

## 模块 3: MCP 功能适配

### 目标

实现 MCP (Model Context Protocol) 的适配层，让 Agent 能够连接外部 MCP Server 获取工具和资源，扩展 Agent 的能力边界。

### 概念定义

MCP 是外部工具服务的标准化接入协议。在本项目中，后端作为 MCP Client，连接一个或多个 MCP Server，将 Server 提供的工具自动转化为 Agent 可用的 FunctionTool。

### 职责

- 实现 MCPToolAdapter，负责连接 MCP Server 和工具转化
- 支持工具自动发现 (连接时获取 Server 的 tool list)
- 将 MCP 工具注册到 Agent 的工具集
- 支持多 MCP Server 配置和管理
- 支持 SSE 和 stdio 两种传输方式

### 非职责

- 不实现 MCP Server (本项目是 Client 角色)
- 不实现 MCP 的 Resource 和 Prompt 协议 (初期仅实现 Tool 协议)

### 配置位置

`configs/mcp.yaml`，配置 MCP Server 列表及连接参数。

### 依赖

依赖 Agent 模式重构完成，MCP 工具注册到 AgentMode 的工具集中。

### 待补充的详细设计

详见 `docs/backend-v2/mcp/` (后续逐步完善)

---

## 模块 4: 对话图片接口

### 目标

支持用户在 Agent/Ask 对话中发送图片，利用 LLM 的 Vision 能力理解图片内容并回答问题。

### 职责

- 实现图片上传 API，返回图片标识
- 扩展 ChatRequest 支持图片引用
- 在 Agent/Ask 模式中将图片作为多模态输入传递给 LLM
- LLM Provider 层适配 Vision 模型调用
- 图片临时存储管理 (存储和清理)

### 非职责

- 不支持 Agent 回答中生成图片 (仅支持用户发图提问)
- 不支持图片 OCR 提取文字后检索 (使用 LLM Vision 直接理解)

### 前置条件

- LLM Provider 支持 Vision (Qwen-VL / ZhipuAI GLM-4V / OpenAI GPT-4o)
- 图片存储依赖 MinIO 或本地临时目录

### API 变更

- 新增: `POST /chat/images/upload` -- 上传对话图片
- 扩展: ChatRequest 增加 `image_ids` 字段

### LLM 兼容性

需要检测当前配置的 LLM 是否支持 Vision。不支持时返回明确的错误提示。
