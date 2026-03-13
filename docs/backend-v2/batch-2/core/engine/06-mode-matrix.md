# Engine 模块：Mode 语义矩阵

## 1. 目标

四种模式共享同一个 workflow runtime，但不共享完全相同的执行语义。

本文件定义 batch-2 的正式规则：

- 共享 `AgentRuntime / workflow loop`
- 差异通过 `ModeConfig = LoopPolicy + ToolPolicy + PromptPolicy + SourcePolicy` 表达
- 不再通过 `BaseMode` 子类分裂执行路径

## 2. 总体原则

### 2.1 同一 runtime，不同 policy

`agent / ask / explain / conclude` 的差异不体现在四套引擎上，而体现在：

- 可用工具集合
- 检索强制程度
- 检索范围策略
- synthesis 阶段是否需要显式切换
- source 展示要求

### 2.2 约束分层

- `LoopPolicy`：控制循环行为、是否强制工具、最大迭代次数、何时进入 synthesis
- `ToolPolicy`：控制工具集合、默认参数模板、scope 规则、质量门控
- `PromptPolicy`：告诉模型应该如何选择工具和组织回答
- `SourcePolicy`：约束前端可见的来源结构和渲染语义

## 3. 模式矩阵

| 维度 | `agent` | `ask` | `explain` | `conclude` |
|------|---------|-------|-----------|------------|
| 角色定位 | 通用任务型 Agent | 文档问答 Agent | 选中文本解释 Agent | 选中文本总结 Agent |
| 输入 | `message` | `message` | `selected_text` 必填，`message` 可选 | `selected_text` 必填，`message` 可选 |
| 工具集 | 内置工具 + 后续 MCP | `knowledge_base + time` | `knowledge_base only` | `knowledge_base only` |
| 执行风格 | `open_loop` | `open_loop` | `retrieval_required_loop` | `retrieval_required_loop` |
| 是否每轮必须调用工具 | 否 | 否 | 是，且必须是 `knowledge_base` | 是，且必须是 `knowledge_base` |
| 最大检索迭代 | 无专属限制，受总迭代保护 | 无专属限制，受总迭代保护 | 3 | 3 |
| 默认检索范围 | notebook / tool 自行决定 | notebook | 当前 `document_id` | 当前 `document_id` |
| 是否允许放宽范围 | 由工具或提示词决定 | 否 | 是，`document -> notebook` | 是，`document -> notebook` |
| 默认检索偏好 | 宽松 | 优先 `knowledge_base` | 更偏精确 / 搜索型 | 更偏 `hybrid` / 更大覆盖 |
| 回答阶段 | 可直接 synthesis | 可直接 synthesis | 必须显式进入 `final_synthesis` | 必须显式进入 `final_synthesis` |
| source 要求 | 统一 source 协议 | 统一 source 协议 | 统一 source 协议，且必须 grounded | 统一 source 协议，且必须 grounded |

## 4. 模式细化

### 4.1 `agent`

`agent` 是开放式模式。它允许：

- 不调用工具直接回答
- 连续多轮调用不同工具
- 未来接入 MCP 工具和 Skill

它的约束最少，但仍遵守统一的 SSE 事件协议和 source 协议。

### 4.2 `ask`

`ask` 仍然是 Agent runtime，而不是特殊的 QueryEngine。

它的关键特征：

- 工具固定为 `knowledge_base + time`
- 不做“每轮必须检索”的硬约束
- 通过 prompt、tool description 和默认工具顺序引导模型优先调用 `knowledge_base`
- 范围默认为 notebook scope

这让 `ask` 既保留了问答场景的 grounded 语义，又不再被 LlamaIndex `ReActAgent` 的执行框架绑定。

### 4.3 `explain`

`explain` 来自当前文档阅读器中的文本选区。

它的关键特征：

- 单次前端触发对应一次请求
- 单次请求内最多 3 次 retrieval iteration
- 每次 retrieval iteration 都必须调用 `knowledge_base`
- 默认先限制在当前 `document_id`
- 如果检索质量不足，后续 iteration 才允许放宽到 notebook scope
- 检索完成后进入单独的 `final_synthesis`

### 4.4 `conclude`

`conclude` 与 `explain` 共享同一类 loop policy，但默认参数更偏向总结和覆盖：

- 默认 `search_type` 更偏 `hybrid`
- 默认 `max_results` 更大
- 允许在一次请求内收集更完整的上下文后再 synthesis

## 5. 推荐的默认配置

### 5.1 `LoopPolicy`

| mode | execution_style | required_tool_name | require_tool_every_iteration | max_retrieval_iterations | max_total_iterations |
|------|-----------------|--------------------|------------------------------|--------------------------|----------------------|
| `agent` | `open_loop` | -- | `false` | `0` | `50` |
| `ask` | `open_loop` | -- | `false` | `0` | `50` |
| `explain` | `retrieval_required_loop` | `knowledge_base` | `true` | `3` | `12` |
| `conclude` | `retrieval_required_loop` | `knowledge_base` | `true` | `3` | `12` |

### 5.2 `ToolPolicy`

| mode | allowed_tool_names | default_tool_name | initial_scope |
|------|--------------------|-------------------|---------------|
| `agent` | 由注册中心和 feature 开关决定 | -- | notebook / mixed |
| `ask` | `knowledge_base`, `time` | `knowledge_base` | notebook |
| `explain` | `knowledge_base` | `knowledge_base` | document |
| `conclude` | `knowledge_base` | `knowledge_base` | document |

## 6. 文档实现要求

实现阶段所有下列文档都必须遵守本矩阵：

- `engine/03-data-model.md`
- `engine/04-dfd-interface.md`
- `engine/07-explain-conclude-retrieval-policy.md`
- `engine/08-retrieval-quality-gates.md`
- `tools/03-tool-contract.md`
- `services/04-api-layer.md`

一旦后续文档与本矩阵冲突，以本文件为准。
