# Engine 模块：架构设计

## 1. 架构总览

Engine 模块由两个核心组件构成：

- **AgentLoop**：通用的 LLM 工具调用循环引擎。不关心业务语义。
- **ModeConfigFactory**：业务语义到执行配置的翻译层。

```
ModeConfigFactory              业务参数 --> 执行配置
       |
       v
AgentLoop                     执行配置 --> StreamEvent 序列
   |         \
LLMClient     Tools[]
   |
AsyncOpenAI (openai SDK)
```

AgentLoop 通过 LLMClient 接口调用 LLM，不直接依赖任何特定 LLM 框架。LLMClient 基于 openai Python SDK 的 AsyncOpenAI 实现，所有 Provider（Qwen、Zhipu、OpenAI）通过 OpenAI 兼容端点接入。

### 1.1 对比当前实现

| 维度 | 当前实现 | 重构后 |
|------|---------|--------|
| 执行引擎 | FunctionAgent、ReActAgent、CondensePlusContextChatEngine 三种 | AgentLoop 一种 |
| 模式差异化 | 继承 BaseMode，各自实现 _process/_stream | ModeConfigFactory 配置驱动 |
| LLM 调用层 | LlamaIndex LLM 抽象（achat_with_tools / astream_chat） | LLMClient 基于 openai SDK（chat / chat_stream） |
| 消息格式 | LlamaIndex ChatMessage | OpenAI 兼容格式（system/user/assistant/tool） |
| Source 收集 | ChatMode 通过 wrapper side-effect，AskMode 独立二次检索 | ToolCallResult 的直接产出 |
| 流式策略 | ChatMode 两阶段（非流式运行 + 流式润色），Explain/Conclude 引擎原生流式 | 工具阶段非流式 + 最终回答流式 |
| 终止条件 | max_iterations 机械限制 | LLM 语义决定 + max_iterations 安全熔断 |
| 错误处理 | 异常上抛，统一中断 | 分类型恢复策略 |

## 2. 设计模式与理由

### 2.1 配置驱动（而非继承驱动）

当前四个 Mode 子类（ChatMode、AskMode、ExplainMode、ConcludeMode）各自实现 _initialize、_process、_stream 方法。每个子类约 200-400 行代码，其中大量是结构相似但细节不同的初始化和处理逻辑。

重构后用 AgentLoopConfig 数据类描述差异，AgentLoop 根据配置行为不同。新增模式只需在 ModeConfigFactory 中添加一组配置，不需要新建类文件。

### 2.2 语义终止（而非机械限制）

AgentLoop 的核心循环终止条件是 LLM 的语义决定：当 LLM 返回的 ChatCompletion 响应中 finish_reason 为 "stop"（无 tool_calls）时，AgentLoop 认为 LLM 已准备好生成最终回答，退出工具调用循环，进入流式输出。

max_iterations 仅作为安全熔断器，默认 50。正常交互中不应触及此上限。如果触及，说明 LLM 行为异常（死循环调用工具），此时产出 ErrorEvent 并终止。

与机械限制（如 Agent=10、Explain=3）的对比：
- 机械限制假设了每种模式的"正常"工具调用次数，但实际取决于任务复杂度。
- Agent 模式处理复杂任务可能需要 15+ 次工具调用，机械限制 10 次会截断有效工作。
- Explain/Conclude 限制 3 次看似合理，但通过 tool_choice 策略（首轮 required + 切 auto）已天然保证快速收敛，不需要额外的迭代限制。

### 2.3 工具调用阶段非流式，最终回答流式

AgentLoop 的工具调用迭代使用 LLMClient.chat()（非流式），仅在 LLM 不再调用工具时切换为 LLMClient.chat_stream()（流式）。

理由：
- 工具调用阶段的 LLM 输出是结构化数据（函数名 + 参数 JSON），用户不需要看到逐 token 生成过程。
- 当前 ChatMode 的两阶段策略（非流式运行 agent + 流式润色输出）需要两次 LLM 调用。重构后只在最终回答时做一次流式调用。
- 全程流式需要在流中区分 tool_call JSON 和最终回答两种状态，增加边界判断复杂度。

通过 PhaseEvent 和 ToolCallEvent 弥补工具阶段用户看不到文本输出的问题——前端据此展示"正在检索..."等状态提示。

### 2.4 tool_choice 切换策略

Explain/Conclude 首轮设 `tool_choice="required"`，工具执行完成后切回 `"auto"`。

这确保 Explain/Conclude 一定先检索文档（不能跳过 RAG 直接回答），同时防止无限循环（切回 auto 后 LLM 可以选择生成最终回答）。

备选方案分析：
- 仅靠 prompt 约束（auto + "务必先检索"）：LLM 可能不遵守，特别是对"已知常识"的选中文本。
- 始终 required：第一轮检索完后，第二轮应该生成回答而非被强制再次调工具。
- 指定具体工具名：过于刚性，未来 Explain/Conclude 可能需要调用其他工具。

### 2.5 错误恢复策略

AgentLoop 对不同类型的错误采用不同的恢复策略，而非统一抛出异常中断执行：

**工具执行失败**：将错误信息封装为 tool role 消息追加到消息链，让 LLM 知道工具调用失败并决定下一步（重试、换工具、或基于已有信息回答）。这是最常见的可恢复错误。

**LLM API 错误（429 / 500 / 超时）**：指数退避重试，最多 3 次。重试间隔：1s, 2s, 4s。超过重试次数后产出 ErrorEvent 终止。

**tool_calls 参数 JSON 解析失败**：将解析错误作为 assistant 消息的反馈追加到消息链，让 LLM 修正输出格式。最多允许 2 次修正尝试。

**不可恢复错误**（认证失败、模型不存在等）：直接产出 ErrorEvent 终止，不重试。

### 2.6 LLMClient 抽象（脱离 LlamaIndex）

当前实现依赖 LlamaIndex 的 LLM 抽象层（achat_with_tools / astream_chat）。重构后 engine 模块通过轻量的 LLMClient 接口调用 LLM，LLMClient 基于 openai Python SDK 的 AsyncOpenAI 实现。

脱离 LlamaIndex 的边界：
- **移除 LlamaIndex**：engine 执行层、LLM 调用层。消息格式改为 OpenAI 兼容格式。
- **保留 LlamaIndex**：RAG 检索层（pgvector VectorStoreIndex、HybridRetriever）、Embedding 层。这些是 LlamaIndex 的核心价值所在。

LLMClient 的详细设计参见 `core/llm/` 模块文档。

### 2.7 parallel_tool_calls 默认关闭

默认 False。工具之间可能存在语义依赖（先检索知识库确认概念，再 Web 搜索补充）。顺序执行更安全。与 Qwen API 的默认值一致。未来如有明确并行场景可在配置中开启。

### 2.8 AgentLoop 无状态

AgentLoop 通过参数接收 chat_history，不持有也不修改任何 Memory 对象。双轨上下文的读写由 context 模块负责，业务状态由 session 模块负责。AgentLoop 作为纯计算组件更容易测试。

## 3. 模块结构与文件布局

```
core/engine/
    __init__.py
    agent_loop.py           AgentLoop 执行引擎
    mode_config.py          ModeConfigFactory + AgentLoopConfig + ModeConfig
    stream_events.py        StreamEvent 类型定义
```

### 3.1 文件职责

**agent_loop.py** -- 执行引擎

AgentLoop 类，实现核心循环。接收 LLMClient 实例、system prompt、工具列表、AgentLoopConfig，暴露 `stream()` 和 `run()` 方法。不依赖任何业务概念。内部实现错误恢复逻辑（工具失败反馈、LLM 重试、JSON 修正）。

**mode_config.py** -- 模式配置

ModeConfigFactory 的 `build()` 方法根据 mode 类型、RAGConfig、selected_text 等参数，返回 ModeConfig（包含 system_prompt、tools、agent_loop_config、user_message）。这是业务语义到执行参数的唯一翻译点。

**stream_events.py** -- 事件类型

StreamEvent 基类和所有子类的定义。纯数据类，无逻辑。

## 4. 架构约束与权衡

### 4.1 OpenAI 兼容 API 依赖

AgentLoop 通过 LLMClient 调用 LLM，LLMClient 使用 openai SDK 的 AsyncOpenAI。所有 Provider 必须提供 OpenAI 兼容的 `/v1/chat/completions` 端点。当前三个 Provider（Qwen/DashScope、Zhipu、OpenAI）均满足此要求。

如果未来某个 Provider 不提供 OpenAI 兼容端点，需要在 llm 模块层面做适配，engine 模块不感知。

### 4.2 tool_choice 兼容性

tool_choice="required" 需要 Provider 支持。Qwen 和 OpenAI 原生支持。如果某个 Provider 不支持 required，需要在 LLMClient 层面做 fallback（如改用强 prompt 约束）。

### 4.3 非流式工具阶段的延迟

工具调用阶段用户看不到 LLM 文本输出。对于耗时较长的工具调用（Web 搜索），等待时间可能数秒。通过 ToolCallEvent/ToolResultEvent 弥补。

### 4.4 Source 提取与工具耦合

不同工具返回不同格式，Source 提取需要知道如何解析每种输出。通过工具注册时附带 Source 提取逻辑解决（在 tools 模块中实现）。

### 4.5 Explain/Conclude 的 Query 质量

LLM 基于 selected_text 提炼检索词的质量依赖 LLM 的指令遵循能力和 system prompt 的设计。这不是额外开销——LLM 在 tool_choice=required 时必须生成工具参数，检索词就是参数之一。
