# Engine 模块：设计目标与职责边界

## 1. 设计目标

### 1.1 统一执行骨架

四种交互模式共享同一个 workflow runtime。模式间差异通过 `LoopPolicy + ToolPolicy + PromptPolicy + SourcePolicy` 驱动，而不是通过四套 mode 子类分别实现。

### 1.2 policy 驱动终止

终止语义不是“所有模式统一自由终止”，而是：

- `agent / ask`：偏开放式语义终止
- `explain / conclude`：retrieval-required loop，单请求内最多 3 次 retrieval iteration，再进入 `final_synthesis`

`max_iterations` 只保留为安全熔断。

### 1.3 Source 作为一等公民

文档引用来源（Source）是工具执行的直接产出。每个工具调用返回结构化的 Source 元数据，AgentLoop 在执行过程中自然累积，最终随响应一起返回给客户端。不存在 side-effect 收集或二次检索。

### 1.4 流式一致性

所有模式产出相同格式的流式事件序列。前端只需实现一套事件处理逻辑。事件类型包括执行阶段标记、工具调用通知、工具结果通知、来源推送、文本增量输出、完成标记。

### 1.5 错误恢复

AgentLoop 对不同类型的错误采用不同的恢复策略，而非统一中断。工具执行失败反馈给 LLM 让其决定下一步；LLM 调用失败则重试；JSON 解析失败反馈给 LLM 让其修正。只有不可恢复的错误才终止执行。

### 1.6 配置驱动的模式差异

四种模式的差异体现在配置维度：

| 维度 | Agent | Ask | Explain | Conclude |
|------|-------|-----|---------|----------|
| 工具集合 | 内置工具 + 后续 MCP | `knowledge_base + time` | `knowledge_base only` | `knowledge_base only` |
| 执行风格 | `open_loop` | `open_loop` | `retrieval_required_loop` | `retrieval_required_loop` |
| 每轮是否必须调用工具 | 否 | 否 | 是，且必须 `knowledge_base` | 是，且必须 `knowledge_base` |
| system prompt | chat.md | ask.md | explain.md | conclude.md |
| 用户消息 | 前端输入 | 前端输入 | 构造自 `selected_text + optional message` | 构造自 `selected_text + optional message` |
| 检索上限 | 受总迭代保护 | 受总迭代保护 | 3 次 retrieval iteration | 3 次 retrieval iteration |

注意：Explain / Conclude 不再采用“首轮 required，后续 auto”。

## 2. 职责

### 2.1 AgentLoop 执行

接收消息和对话历史（由 context 模块构建，OpenAI 兼容格式），通过 LLMClient 驱动 LLM 进行推理、工具调用和最终 synthesis。Explain / Conclude 会在每轮检索后执行质量门控。

循环终止条件：LLM 返回不含 tool_calls 的响应（语义终止）。安全熔断：max_iterations 次迭代后强制终止。

### 2.2 模式配置构建

ModeConfigFactory 根据 mode 类型和请求参数（RAGConfig、selected_text、source_document_ids），产出 runtime 所需的全部配置：system prompt、LoopPolicy、ToolPolicy、构造后的用户消息。

### 2.3 流式事件产出

在执行过程中产出结构化的 StreamEvent 异步生成器。事件序列反映真实执行进度，供上层（API Router）转换为 SSE 推送。

### 2.4 Source 收集

在每次工具调用完成后，从工具返回值中提取 Source 元数据并累积。Source 随 ToolResultEvent 产出，不等到最终完成。

### 2.5 取消处理

响应外部取消信号。在工具调用之间的检查点检测取消，停止后续执行。不强制中断正在执行的原子操作，等待当前操作完成后退出。

### 2.6 错误恢复

根据错误类型执行对应的恢复策略：

| 错误类型 | 恢复策略 |
|---------|---------|
| 工具执行失败 | 将错误信息作为 tool message 反馈给 LLM，由 LLM 决定重试、换工具或直接回答 |
| LLM 429/超时 | 指数退避重试（最多 3 次），超过后产出 ErrorEvent 终止 |
| tool_calls JSON 解析失败 | 将解析错误反馈给 LLM，让其修正输出格式 |
| 不可恢复错误 | 产出 ErrorEvent，终止执行 |

## 3. 非职责

### 3.1 上下文管理

Engine 不管理对话历史、不做 token 预算分配、不执行压缩。它接收 context 模块构建好的 OpenAI 兼容格式消息列表（`List[ChatCompletionMessageParam]`），不关心消息链如何组装。

### 3.2 会话管理

Engine 不管理会话生命周期、不做消息持久化。它是无状态的计算单元。

### 3.3 工具实现

Engine 不实现具体工具（RAG 检索、Web 搜索等）。它接收工具列表作为参数，调用工具的标准接口。

### 3.4 HTTP 协议

Engine 不处理 HTTP 请求/响应、不管理 SSE 连接。它产出 AsyncGenerator[StreamEvent]，由 API 层转换为 SSE。

### 3.5 LLM 调用细节

Engine 不管理 LLM Provider 选择、API 密钥、base_url 配置。它通过 LLMClient 接口调用 LLM，具体的 Provider 适配由 llm 模块负责。
