# 第二批：AI Core 重构层

本批次的主目标不是继续给现有聊天能力打补丁，而是完成 AI Runtime 的核心重构：

- 将 `Agent / Ask / Explain / Conclude` 统一迁移到自研 workflow runtime
- 脱离 LlamaIndex 在执行层、消息层、记忆层的依赖
- 建立自研的 `llm + context + engine + session + tools`
- 为后续 MCP 接入、Skill 系统和图片能力打基础

`batch-2` 是 `backend-v2` 下的一个大阶段，允许再拆成多个小阶段、多次 commit 落地。

---

## 整体架构变更

### 重构前

```
ChatMode(FunctionAgent)   AskMode(ReActAgent)   ExplainMode(QueryEngine)   ConcludeMode(QueryEngine)
         \                      |                       |                       /
          ------ LlamaIndex Agent / ChatEngine / Memory / LLM 抽象混合驱动 ------
```

### 重构后

```
ModeConfigFactory
       |
Workflow Runtime (统一执行骨架)
   |              |                \
LoopPolicy        ToolPolicy        SourcePolicy
   |
LLMClient --------------------- ToolRegistry
   |                                 |        \
AsyncOpenAI (openai SDK)        BuiltinTools   MCPTools
   |
Provider (Qwen / Zhipu / OpenAI)
```

### 关键设计决策汇总

| 决策 | 结论 |
|------|------|
| 执行引擎 | 统一 workflow runtime，模式差异通过 `ModeConfig = LoopPolicy + ToolPolicy + PromptPolicy + SourcePolicy` 表达 |
| 模式策略 | `同一 runtime，不同 policy`，不再用四套独立引擎 |
| Agent 行为 | `agent` 宽松开放，`ask` 偏知识库问答，`explain / conclude` 使用 retrieval-required loop |
| LLM 调用层 | LLMClient 基于 openai SDK AsyncOpenAI，脱离 LlamaIndex |
| 消息格式 | OpenAI 兼容格式（system/user/assistant/tool） |
| 错误恢复 | 分类型策略：工具失败反馈 LLM、LLM 429 指数退避重试、invalid tool output repair |
| 工具管理 | ToolRegistry 应用级单例，合并 BuiltinToolProvider + MCPClientManager |
| MCP 协议 | 仅 `agent` 模式，stdio + HTTP Streamable，放在 batch-2 后段 |
| LlamaIndex 边界 | 移除 runtime / QueryEngine / Memory；保留 retrieval、vector store、embedding |
| 上下文管理 | 先落最小版：双轨内存 + truncation + lock；高级压缩后续增强 |

---

## 模块 1: Core 重构（5 个子模块）

将现有 `core/engine/` 拆分为 5 个职责清晰的模块。

### 1.1 Engine -- 执行引擎 / Workflow Runtime

**目标**：统一四模式执行路径，消除引擎分裂。

四种交互模式共享同一个 workflow runtime，差异通过 ModeConfigFactory 产出的 policy 体现：

| 维度 | Agent | Ask | Explain | Conclude |
|------|-------|-----|---------|----------|
| 工具集合 | 内置工具 + MCP（后段） | `knowledge_base + time` | `knowledge_base only` | `knowledge_base only` |
| 执行风格 | `open_loop` | `open_loop` | `retrieval_required_loop` | `retrieval_required_loop` |
| 每轮是否必须调用工具 | 否 | 否 | 是，且必须 `knowledge_base` | 是，且必须 `knowledge_base` |
| 单请求内最大检索迭代 | -- | -- | 3 | 3 |
| 默认范围 | notebook / mixed | notebook | 当前 `document_id` | 当前 `document_id` |
| system prompt | chat.md | ask.md | explain.md | conclude.md |
| 用户消息 | 前端输入 | 前端输入 | `selected_text` + 可选 message | `selected_text` + 可选 message |

核心组件：
- **Workflow Runtime**：统一执行骨架。Agent/Ask 宽松，Explain/Conclude 强约束。
- **ModeConfigFactory**：业务参数到 `LoopPolicy + ToolPolicy + PromptPolicy + SourcePolicy` 的翻译。
- **StreamEvent**：统一事件协议（`start / warning / phase / tool_call / tool_result / sources / content / done / error / heartbeat`）。

详细设计：`docs/backend-v2/batch-2/core/engine/`

### 1.2 LLM -- LLM 调用层

**目标**：脱离 LlamaIndex LLM 抽象，基于 openai SDK 直接调用 OpenAI 兼容 API。

- **LLMClient**：AsyncOpenAI 的薄封装，暴露 `chat()` 和 `chat_stream()`。
- **LLMClientFactory**：根据当前 provider/model 配置创建 LLMClient 实例。
- **Provider 统一**：Qwen、Zhipu、OpenAI 三个 Provider 通过相同的 AsyncOpenAI + 不同的 base_url/api_key 接入，不需要各自的子类。

LlamaIndex 脱离边界：
- 移除：engine 执行层、LLM 调用层。消息格式改为 OpenAI 兼容 dict。
- 保留：RAG 检索层（pgvector VectorStoreIndex、HybridRetriever）、Embedding 层。

详细设计：`docs/backend-v2/batch-2/core/llm/`

### 1.3 Context -- 上下文管理

**目标**：在第一版先落最小可用上下文系统，而不是一次性做满所有压缩能力。

- **第一版必须有**：双轨内存（Main / Side）、确定性截断、session lock、消息链构建
- **后续增强**：分层压缩、异步摘要、预算细调

详细设计：`docs/backend-v2/batch-2/core/context/`

### 1.4 Session -- 会话管理

**目标**：会话生命周期管理、消息持久化协调、并发控制。

详细设计：`docs/backend-v2/batch-2/core/session/`

### 1.5 Tools -- 工具层

**目标**：统一工具注册中心，合并内置工具和 MCP 外部工具。

- **ToolRegistry**：应用级单例，统一返回 `ToolDefinition`
- **BuiltinToolProvider**：按 mode 提供内置工具集合
- **knowledge_base 工具**：统一 RAG 检索工具，支持 `hybrid / semantic / keyword`
- **统一工具协议**：`ToolDefinition + ToolCallResult + SourceItem + ToolQualityMeta`

详细设计：`docs/backend-v2/batch-2/core/tools/`

### 模块依赖关系

```
session --> engine, context       session 创建 AgentLoop，调 context 读写历史
engine  --> llm, tools            AgentLoop 通过 LLMClient 调 LLM，使用 ToolDefinition 列表
tools   --> mcp                   ToolRegistry 合并内置工具和 MCP 工具
context --> llm                   Compressor 使用 LLMClient 生成摘要
llm     --> config                从 llm.yaml 和环境变量加载配置
```

---

## 模块 2: MCP 功能适配（batch-2 后段）

### 目标

实现 MCP (Model Context Protocol) Client，让 `agent` 模式能够连接外部 MCP Server 获取工具，扩展能力边界。仅 `agent` 模式接入 MCP，Ask/Explain/Conclude 不涉及。

### 设计决策

| 决策 | 结论 |
|------|------|
| 传输方式 | 同时支持 stdio 和 HTTP Streamable |
| 配置格式 | mcp.json，与 Claude Code 协议对齐 |
| 配置管理 | 静态配置文件，前端 Settings 面板仅控制开关 |
| 加载策略 | 应用启动时连接，懒加载（用户启用 MCP 时触发） |
| 工具注册 | 通过 ToolRegistry 统一管理，MCP 工具与内置工具同等对待 |
| 作用范围 | 全局生效 |

### 核心组件

- **MCPConfigLoader**：读取 mcp.json，解析环境变量占位符。
- **MCPClientManager**：管理 MCP Server 连接生命周期，提供工具列表。
- **MCPToolAdapter**：将 MCP Server 工具转换为 ToolDefinition。

### 配置示例

```json
{
  "mcpServers": {
    "local-tool": {
      "command": "python",
      "args": ["-m", "my_tool_server"],
      "env": { "API_KEY": "${MY_API_KEY}" }
    },
    "remote-service": {
      "type": "http",
      "url": "https://api.example.com/mcp",
      "headers": { "Authorization": "Bearer ${SERVICE_TOKEN}" }
    }
  }
}
```

详细设计：`docs/backend-v2/batch-2/mcp/`

---

## 模块 3: Skill 系统（移至 batch-3）

### 目标

实现 Skill 机制，为 Agent 提供预定义的任务流能力。Skill 是"prompt + tool 组合"的封装，Agent 遇到特定场景时调用对应 Skill。

### 状态

不在 batch-2 实施。Skill 依赖新 runtime 稳定后再接入，避免与 core 重构互相耦合。

### 依赖

依赖 Core 重构完成（AgentLoop + ToolRegistry），Skill 将通过独立机制接入 AgentLoop。

### 待补充的详细设计

详见 `docs/backend-v2/batch-2/skills/`（预留，正式设计放到 batch-3）

---

## 模块 4: 对话图片接口（移至 batch-3）

### 目标

不在 batch-2 实施。图片输入依赖新消息协议、多模态兼容和 MinIO 运行时稳定后再推进。

### 职责

- 实现图片上传 API，返回图片标识
- 扩展 ChatRequest 支持图片引用
- 在 Agent/Ask 模式中将图片作为多模态输入传递给 LLM（OpenAI 兼容格式的 image_url content part）
- 图片临时存储管理（存储和清理）

### 非职责

- 不支持 Agent 回答中生成图片（仅支持用户发图提问）
- 不支持图片 OCR 提取文字后检索（使用 LLM Vision 直接理解）

### 前置条件

- LLM Provider 支持 Vision（Qwen-VL / ZhipuAI GLM-4V / OpenAI GPT-4o）
- 图片存储依赖 MinIO

## 服务层适配

Core 重构后，Application Services 层需要适配新的模块接口。

详细设计：`docs/backend-v2/batch-2/services/`

| 文档 | 说明 |
|------|------|
| 01-blocking-fix | 文档处理阻塞逻辑修复（独立于 core 重构） |
| 02-chat-service-refactor | ChatService 适配 AgentLoop + SessionManager |
| 03-dependency-injection | DI 层变更（LLMClient、ToolRegistry 等单例注入） |
| 04-api-layer | API 路由、SSE 协议适配新 StreamEvent |

---

## 实施顺序

```
0. 文档冻结：mode matrix、message contract、tool contract、retrieval quality gates、migration phases

1. blocking-fix（独立收益项）

2. Core 重构
   llm -> tools -> context -> engine -> session

3. 服务层适配
   chat-service -> DI -> API

4. 模式迁移
   agent -> ask -> explain/conclude

5. 删除旧 core
   modes/ -> selector.py -> core/agent/ -> old session manager

6. MCP 功能适配（依赖 tools/ToolRegistry）

7. batch-3 再做 Skill / 图片接口
```

## 详细设计文档索引

| 模块 | 路径 | 状态 |
|------|------|------|
| Engine | `docs/backend-v2/batch-2/core/engine/` | 已完成 |
| LLM | `docs/backend-v2/batch-2/core/llm/` | 已完成 |
| Context | `docs/backend-v2/batch-2/core/context/` | 已完成 |
| Session | `docs/backend-v2/batch-2/core/session/` | 已完成 |
| Tools | `docs/backend-v2/batch-2/core/tools/` | 已完成 |
| MCP | `docs/backend-v2/batch-2/mcp/` | 已完成 |
| Services | `docs/backend-v2/batch-2/services/` | 已完成 |
| Skill | `docs/backend-v2/batch-2/skills/` | 延后到 batch-3 |
| 图片接口 | -- | 延后到 batch-3 |
