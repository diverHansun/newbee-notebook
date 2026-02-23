# P4: 两阶段流式输出

## 问题描述

Chat 模式使用流式输出时，`ChatMode._stream()` 直接调用 `LLM.astream_chat()` 绕过了 FunctionAgent，导致 LLM 无法实际执行 Tool 调用。但 LLM 在输出中可能生成 Tool 调用的格式文本（如搜索查询语句、JSON 格式的 function call），这些中间文本直接流到前端显示，造成用户看到未完成的搜索指令等异常内容。

`chat_mode.py` 第 158-162 行的注释已明确说明：

```
This bypasses the FunctionAgent to provide true token-by-token streaming.
Tool calling is not supported in streaming mode; use _process() for that.
```

## 根因分析

### 当前 Chat 模式的两条路径

| 路径 | 方法 | Tool 支持 | 流式输出 |
|------|------|----------|---------|
| 非流式 | `_process()` | 有（FunctionAgent） | 无 |
| 流式 | `_stream()` | 无（直接 LLM） | 有 |

流式路径完全绕过了 Agent，因此 LLM 在需要调用工具时只能输出工具调用的"意图文本"而非实际执行结果。

### Ask 模式的参考实现

Ask 模式的 `_stream()` 方法（`ask_mode.py` 第 358-373 行）已经采用了类似的两阶段策略：先通过 `_process()` 执行完整的 ReActAgent（包含 RAG 检索），再用 `astream_chat()` 流式输出最终回答。Chat 模式需要对齐此模式。

## 设计方案：两阶段流式

### 核心思路

将 `ChatMode._stream()` 重写为两个阶段：

```
阶段 1（Agent 执行）: 调用 FunctionAgent 完成 Tool 调用，获取完整上下文
阶段 2（流式输出）: 将 Tool 结果注入 messages，调用 LLM 流式生成最终回答
```

### 阶段 1: Agent 执行

```python
async def _stream(self, message: str) -> AsyncGenerator[str, None]:
    await self._ensure_runner_scope()

    chat_history = []
    if self._memory is not None:
        chat_history = self._memory.get_all()
    chat_history = self._augment_chat_history_with_ec_summary(chat_history)

    # 阶段 1: 通过 FunctionAgent 执行，获取完整的 tool 调用结果
    try:
        agent_response = await self._runner.run(
            message=message,
            chat_history=chat_history,
        )
    except Exception:
        raise
```

此阶段期间，前端通过 `thinking` 事件显示思考指示器（参见 P2 文档）。

### 阶段 2: 流式输出

```python
    # 阶段 2: 构建包含 tool 结果的 messages，流式生成最终回答
    messages: List[ChatMessage] = []

    system_prompt = self._config.system_prompt or ""
    if system_prompt:
        messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))

    if self._memory is not None:
        messages.extend(self._memory.get_all())
    messages = self._augment_chat_history_with_ec_summary(messages)

    # 注入 agent 执行结果作为上下文
    messages.append(ChatMessage(role=MessageRole.USER, content=message))
    messages.append(ChatMessage(
        role=MessageRole.ASSISTANT,
        content=agent_response,
    ))
    messages.append(ChatMessage(
        role=MessageRole.USER,
        content="请基于以上信息，直接回答用户的问题。",
    ))

    # 流式输出
    full_response = ""
    stream_response = await self._llm.astream_chat(messages)
    async for chunk in stream_response:
        delta = getattr(chunk, "delta", None)
        if delta:
            full_response += delta
            yield delta

    # 存入 memory
    if self._memory is not None and full_response:
        self._memory.put(ChatMessage(role=MessageRole.USER, content=message))
        self._memory.put(ChatMessage(role=MessageRole.ASSISTANT, content=full_response))

    self._last_sources = self._collect_sources(message)
```

### chat_service.py 中的 thinking 事件编排

`thinking` 事件的 SSE 格式定义和前端处理逻辑见 [P2 文档](P2-thinking-indicator.md)。P4 的贡献在于确定 **触发时机**：阶段 1（Agent 搜索）开始时发送 `searching`，阶段 2（LLM 流式生成）开始前发送 `generating`。两个时间点通过下文的 PHASE_MARKER 机制传递给 `chat_service.py`。

### thinking 事件的触发机制

为了让 `chat_service` 能在正确的时机发送 thinking 事件，`_stream()` 方法需要通过 yield 标记阶段边界：

```python
# 在 _stream() 中使用特殊标记区分阶段
PHASE_MARKER = "__PHASE__"

async def _stream(self, message: str) -> AsyncGenerator[str, None]:
    yield f"{PHASE_MARKER}:searching"   # 标记进入搜索阶段

    agent_response = await self._runner.run(...)

    yield f"{PHASE_MARKER}:generating"  # 标记进入生成阶段

    # ... 流式输出 content chunks ...
```

`chat_service.py` 在迭代 mode stream 时检测 PHASE_MARKER 前缀，将其转换为 thinking 事件，非标记字符串作为 content 事件处理。

> **防御要求：fallback 路径过滤**
>
> `chat_service._chat_via_stream_fallback()`（第 231 行）直接将 mode stream 的输出拼接为 `full_response`。
> 若 `_stream()` yield 出了 PHASE_MARKER 字符串，它们会混入最终的非流式回复内容。
> 必须在 fallback 的迭代循环中同样进行过滤：
>
> ```python
> # _chat_via_stream_fallback() 内的迭代循环需要增加过滤
if not chunk.startswith(PHASE_MARKER):
>     full_response += chunk
> ```
>
> 这是批次 B 实施时必须同完成的防御项。

### 前端降级触发条件补充（回归修复）

`chat_service.py` 的 chunk 超时不会中断 HTTP 连接，而是通过 SSE 事件返回：

```json
{"type":"error","error_code":"timeout","message":"Stream timeout"}
```

这意味着前端 **不会进入 `fetch`/解析异常的 `onError` 分支**，而是先收到一个正常的 `error` 事件再结束流。

因此前端在 `useChatSession.ts` 中必须补充一条规则：

- 当 `onEvent(error)` 且 `error_code === "timeout"` 时，按“流式超时”处理
- 复用现有非流式 `/chat` fallback 逻辑（而不是直接把消息标记为 error）

否则会出现 `Ask` 模式（以及潜在的 `Chat` 模式）在 SSE 超时时前端直接显示 `[timeout] Stream timeout`，但没有自动降级的回归问题。

### 优化：无 Tool 调用时的快速路径

如果 FunctionAgent 判断不需要调用任何 Tool，阶段 1 的 agent_response 本身就是最终回答。此时可以跳过阶段 2，直接将 agent_response 拆分为 chunks yield 出去，避免不必要的二次 LLM 调用。

判断方式：检查 `self._runner` 在本次执行中是否触发了 tool call。可通过 FunctionAgentRunner 暴露一个 `last_tool_calls` 属性实现。

```python
agent_response = await self._runner.run(...)

if not self._runner.had_tool_calls:
    # 快速路径：直接输出 agent response
    for i in range(0, len(agent_response), 20):
        yield agent_response[i:i+20]
else:
    # 完整路径：阶段 2 流式重新生成
    # ... 如上 ...
```

### Explain/Conclude 模式

这两个模式使用 `CondensePlusContextChatEngine`，不涉及 FunctionAgent 和 Tool 调用，流式路径无此问题，不需要修改。

## 涉及文件

| 文件 | 修改内容 |
|------|----------|
| `newbee_notebook/core/engine/modes/chat_mode.py` | `_stream()` 重写为两阶段 |
| `newbee_notebook/core/agent/function_agent.py` | 暴露 `had_tool_calls` 属性 |
| `newbee_notebook/application/services/chat_service.py` | thinking 事件编排、0PHASE_MARKER 解析；**`_chat_via_stream_fallback()` 过滤 PHASE_MARKER**（防守） |
| `newbee_notebook/api/routers/chat.py` | SSEEvent.thinking() 格式化 |

## 验证标准

- Chat 模式流式输出中不再出现 Tool 调用的格式文本
- 需要 Tool 调用时，前端显示 thinking 指示器，Tool 执行完成后开始流式输出内容
- 不需要 Tool 调用时，走快速路径，延迟与当前相当
- Ask 模式行为不变（已有类似架构）
- Explain/Conclude 模式行为不变
- SSE 事件序列完整：start -> thinking(searching) -> thinking(generating) -> content... -> sources -> done
- **超时降级补充**：当后端通过 SSE 返回 `error(timeout)` 时，前端仍会自动触发非流式 `/chat` fallback（而不是直接停留在错误态）
