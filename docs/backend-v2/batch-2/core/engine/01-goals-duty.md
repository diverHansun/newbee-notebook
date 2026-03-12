# Engine 模块：设计目标与职责边界

## 1. 设计目标

### 1.1 统一执行路径

四种交互模式共享同一个 AgentLoop 执行引擎。模式间的行为差异完全通过配置参数（工具列表、tool_choice 策略、system prompt）驱动。新增交互模式只需定义一组新的配置参数。

### 1.2 语义终止

AgentLoop 的终止由 LLM 语义决定：当 LLM 返回的响应不包含 tool_calls 时，循环结束，进入最终回答的流式输出阶段。max_iterations 仅作为安全熔断器存在，防止 LLM 陷入无限工具调用循环。这意味着 AgentLoop 不预设"应该调用几次工具"，而是让 LLM 根据任务复杂度自行决定何时给出最终回答。

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
| 工具集合 | RAG, ES, Web, Time | RAG, ES, Web, Time | RAG, ES | RAG, ES |
| tool_choice | auto | auto | required (首轮) | required (首轮) |
| system prompt | chat.md | ask.md | explain.md | conclude.md |
| 用户消息 | 前端输入 | 前端输入 | 构造自 selected_text | 构造自 selected_text |
| 安全熔断 | 50 次迭代 | 50 次迭代 | 50 次迭代 | 50 次迭代 |

注意：max_iterations 对所有模式统一为安全熔断值（50），不作为功能性限制。Explain/Conclude 通过 tool_choice 首轮 required + 第二轮切 auto 的策略，由 LLM 语义决定何时结束，通常 2-3 轮即完成。

## 2. 职责

### 2.1 AgentLoop 执行

接收消息和对话历史（由 context 模块构建，OpenAI 兼容格式），通过 LLMClient 驱动 LLM 进行工具调用循环。每次循环：调用 LLM -> 检查响应中的 tool_calls -> 若有则执行工具并追加结果到消息链 -> 继续循环 -> 若无则进入流式输出最终回答。

循环终止条件：LLM 返回不含 tool_calls 的响应（语义终止）。安全熔断：max_iterations 次迭代后强制终止。

### 2.2 模式配置构建

ModeConfigFactory 根据 mode 类型和请求参数（RAGConfig、selected_text、source_document_ids），产出 AgentLoop 所需的全部配置：system prompt、工具列表、AgentLoopConfig、构造后的用户消息。

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
