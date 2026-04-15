# AI Message 中间态消息 — 后端开发计划

## 概述

本文档描述后端如何支持 Agent Loop 的中间态消息（Intermediate Content）功能：让 LLM 在 reasoning 阶段产出的伴随文本（与 tool_calls 同时返回的 content）能够被实时传递给前端，而不是像现在一样被丢弃。

与前端分析文档（`../frontend/intermediate-content-plan.md`）配合阅读，两者分别描述同一功能的前后端实现。

---

## 一、现状分析

### 1.1 当前行为

**文件**：`newbee_notebook/core/engine/agent_loop.py`，第 400–473 行

reasoning 阶段调用 `_chat_with_retry()`，底层是 `llm_client.chat()`（非流式）：

```python
response = await self._chat_with_retry(
    messages=messages,
    tools=tool_specs or None,
    tool_choice=forced_tool_choice or self._required_tool_choice(),
    disable_thinking=True,
)
tool_calls = self._extract_tool_calls(response)
assistant_content = self._extract_message_content(response).strip()
```

当 LLM 同时返回 `content` 和 `tool_calls` 时，content 被丢弃：

```python
# agent_loop.py 第 254–256 行
@staticmethod
def _assistant_tool_message(tool_calls):
    return {"role": "assistant", "content": None, "tool_calls": tool_calls}
```

`content` 被硬编码为 `None`，伴随文本完全丢失。

### 1.2 LLM 接口的实际行为

根据 Zhipu API 文档（`docs/LLM-interface/zhipu-chatCompletion.md`，第 281 行）：

> 当提供此字段(tool_calls)时，`content`**通常**为空。

关键词是"通常"。LLM 完全可以在返回 tool_calls 的同时包含有意义的 content，例如：

```
content: "让我来查看一下知识库中的相关内容"
tool_calls: [{ function: { name: "knowledge_base", arguments: ... } }]
```

### 1.3 当前数据流

```
LLM.chat()（非流式）
  → response 包含 content + tool_calls
    → content 被丢弃（_assistant_tool_message 设 content=None）
    → tool_calls 被执行
      → 工具结果写入 messages
        → 下一轮 reasoning 或进入 synthesis
          → synthesis 阶段使用 chat_stream() 流式输出最终回答
```

用户在 reasoning 阶段只能看到 spinner 或 ToolStepsIndicator，无法看到 LLM 的中间态思考文本。

---

## 二、优化目标

1. reasoning 阶段从非流式 `chat()` 切换为流式 `chat_stream()`，实时接收 content delta
2. 在流中正确拼装分块返回的 tool_calls delta
3. 通过新的 `IntermediateContentEvent` 将中间态 content 逐 token 传递给前端
4. 保留现有非流式 `_chat_with_retry()` 接口，不破坏 `run()` 方法和现有测试
5. 将伴随文本正确写入 messages 历史（不再设为 None），保持对话上下文完整

---

## 三、数据流修改

### 3.1 修改后的数据流

```
LLM.chat_stream()（流式）
  → 逐 chunk 迭代：
    ├─ content delta → yield IntermediateContentEvent(delta=...) → SSE → 前端
    └─ tool_call delta → 按 index 拼装到 _ToolCallAccumulator
  → 流结束：
    ├─ 完整 content（拼接所有 delta）
    ├─ 完整 tool_calls（从 accumulator 构建）
    └─ 继续现有逻辑：执行工具、下一轮或 synthesis
```

### 3.2 事件流对比

| 阶段 | 修改前 | 修改后 |
|---|---|---|
| reasoning 开始 | `PhaseEvent("reasoning")` | `PhaseEvent("reasoning")`（不变） |
| LLM 返回中间态文本 | **无** | `IntermediateContentEvent(delta=...)` × N |
| tool_call 开始 | `ToolCallEvent(...)` | `ToolCallEvent(...)`（不变） |
| tool 执行完成 | `ToolResultEvent(...)` | `ToolResultEvent(...)`（不变） |
| 最终回答 | `ContentEvent(delta=...)` | `ContentEvent(delta=...)`（不变） |

### 3.3 消息历史修改

修改前：

```python
# tool_calls 存在时，content 被强制设为 None
{"role": "assistant", "content": None, "tool_calls": [...]}
```

修改后：

```python
# 保留 LLM 实际返回的 content
{"role": "assistant", "content": "让我查看一下知识库", "tool_calls": [...]}
```

---

## 四、实施方案

### 4.1 新增 IntermediateContentEvent

**文件**：`newbee_notebook/core/engine/stream_events.py`

```python
@dataclass(frozen=True)
class IntermediateContentEvent:
    """LLM reasoning 阶段伴随 structured tool_calls 产出的中间态文本 delta。"""
    delta: str
    event: str = "intermediate_content"
```

### 4.2 新增 Tool Call Delta 拼装器

**文件**：`newbee_notebook/core/engine/agent_loop.py`

新增内部数据类用于跟踪流式 tool_call 的分块拼装：

```python
@dataclass
class _ToolCallAccumulator:
    """跟踪单个 structured tool_call 的流式 delta 拼装状态。"""
    id: str = ""
    type: str = "function"
    name: str = ""
    arguments: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "function": {
                "name": self.name,
                "arguments": self.arguments,
            },
        }
```

拼装逻辑：每收到一个 delta chunk，按 `index` 定位到对应的 accumulator，追加 `id`、`name` 和 `arguments` 片段。

OpenAI 兼容 API 的流式 tool_calls 格式：

```json
// chunk 1: 首次出现，带 id 和 function name
{"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_xxx","type":"function","function":{"name":"knowledge_base","arguments":""}}]}}]}

// chunk 2~N: 后续只有 arguments 增量
{"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\"query\":"}}]}}]}
{"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\"什么是AI\"}"}}]}}]}
```

### 4.3 新增 _stream_reasoning() 方法

**文件**：`newbee_notebook/core/engine/agent_loop.py`

新增异步生成器方法，替代 reasoning 阶段的 `_chat_with_retry()` 调用：

```python
@dataclass
class _StreamReasoningResult:
    """_stream_reasoning() 完成后的聚合结果。"""
    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    used_structured_tool_calls: bool = False
    emitted_intermediate: bool = False

async def _stream_reasoning(
    self,
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    tool_choice: Any,
    result: _StreamReasoningResult,
) -> AsyncGenerator[IntermediateContentEvent, None]:
```

职责：

1. 调用 `self._llm_client.chat_stream(messages=..., tools=..., tool_choice=..., disable_thinking=True)`。
2. 逐 chunk 迭代流，使用**延迟 flush 策略**：
   - 提取 `delta.content`，先暂存到 `content_buffer`。
   - 提取 `delta.tool_calls`，按 `index` 追加到 `_ToolCallAccumulator`。
   - **首次看到 structured tool_call delta 时**，把已缓冲的 `content_buffer` 一次性 flush 为 `IntermediateContentEvent`；之后新的 content delta 直接 yield。
3. 流结束后：
   - 若已有 structured tool_calls，则把聚合后的 `content` 和 `tool_calls` 写入 `result`。
   - 若没有 structured tool_calls，则保留完整 `content`，并继续复用现有 `_parse_textual_tool_calls()` 兜底解析文本型 tool_call 标记。

**延迟 flush 的原因**：OpenAI 兼容 API 中，content delta 往往先于 tool_call delta 到达。如果一开始就对外发送 content delta，那么“直接回答”场景会先被当成中间态展示，再被当成终结态展示，造成重复。延迟到确认出现 structured tool_call 后再 flush，才能精确区分：

- **有 structured tool_calls**：buffer 中的文本是中间态，发送 `IntermediateContentEvent`。
- **无 structured tool_calls**：buffer 中的文本继续当作终结态候选，保持当前行为。

**retry 约束**：

- 只有在 `_stream_reasoning()` **尚未向外 yield 任何业务事件** 前，才允许重试整个流式调用。
- 一旦已经发出 `IntermediateContentEvent`，就不再重试，直接抛错并结束本轮，避免前端看到重复中间态或重复工具步骤。

**delta 提取方法**：

新增 `_extract_stream_tool_call_deltas()` 静态方法，从单个 chunk 中提取 tool_call delta 列表：

```python
@staticmethod
def _extract_stream_tool_call_deltas(chunk: Any) -> list[dict[str, Any]]:
    """从流式 chunk 中提取 tool_call delta 片段。"""
    choice = AgentLoop._extract_choice(chunk)
    if isinstance(choice, dict):
        delta = choice.get("delta") or {}
        return list(delta.get("tool_calls") or [])
    delta = getattr(choice, "delta", None)
    if delta is None:
        return []
    tool_calls = getattr(delta, "tool_calls", None)
    return list(tool_calls) if tool_calls else []
```

### 4.4 修改主循环 stream() 方法

**文件**：`newbee_notebook/core/engine/agent_loop.py`

**修改前**：

```python
yield PhaseEvent(stage="reasoning")
response = await self._chat_with_retry(
    messages=messages,
    tools=tool_specs or None,
    tool_choice=forced_tool_choice or self._required_tool_choice(),
    disable_thinking=True,
)
iterations += 1
tool_calls = self._extract_tool_calls(response)
assistant_content = self._extract_message_content(response).strip()
```

**修改后**：

```python
yield PhaseEvent(stage="reasoning")
reasoning_result = _StreamReasoningResult()

async for intermediate_event in self._stream_reasoning(
    messages=messages,
    tools=tool_specs or None,
    tool_choice=forced_tool_choice or self._required_tool_choice(),
    result=reasoning_result,
):
    yield intermediate_event

iterations += 1
tool_calls = reasoning_result.tool_calls
assistant_content = reasoning_result.content.strip()
```

后续主循环逻辑整体不变，仍然沿用现有的 repair、tool 执行、synthesis 切换策略。

### 4.5 修改 assistant tool message 的写回策略

**文件**：`newbee_notebook/core/engine/agent_loop.py`

保留 `_assistant_tool_message()` 的扩展签名：

```python
@staticmethod
def _assistant_tool_message(tool_calls, content=None):
    return {"role": "assistant", "content": content, "tool_calls": tool_calls}
```

但写回策略需要区分两类 tool_call：

1. **structured tool_calls**：若模型同时返回自然语言 content，则保留到 messages 历史中。
2. **文本型 tool_call 标记**：若 tool_call 是通过 `_parse_textual_tool_calls()` 从原始 content 中解析出来的，则**不要把原始 markup content 原样写回历史**，避免 `<tool_call>...</tool_call>` 协议文本污染上下文。

调用处建议写成：

```python
assistant_tool_content = assistant_content or None
if tool_calls and not reasoning_result.used_structured_tool_calls:
    assistant_tool_content = None

messages.append(
    self._assistant_tool_message(tool_calls, content=assistant_tool_content)
)
```

### 4.6 SSE 适配层修改

**文件**：`newbee_notebook/application/services/chat_service.py`

在 `chat_stream()` 方法的事件转发循环中新增：

```python
elif isinstance(event, IntermediateContentEvent):
    yield {"type": "intermediate_content", "delta": event.delta}
```

**文件**：`newbee_notebook/api/routers/chat.py`

`sse_adapter()` 已经有通用透传分支，因此无需新增专门格式化方法：

```python
yield SSEEvent.format("intermediate_content", payload)
```

### 4.7 V1 范围说明

本次改造只解决“带 tool_calls 的 reasoning 中间态可见”问题，不顺带改造“无 tool_call 的直接回答首字流式体验”。也就是说：

- **有 structured tool_call + content**：前端能实时看到中间态。
- **只有 content、没有 tool_call**：仍然保持当前最终回答路径，不额外提前暴露 reasoning 首字。

这是刻意的范围控制，优先保证状态正确、避免重复展示。

---

## 五、边界情况处理

| 场景 | 处理方式 |
|---|---|
| LLM 返回 structured tool_calls 但无 content | 不产生 `IntermediateContentEvent`，行为与当前一致 |
| LLM 只返回 content 无 tool_calls（直接回答） | 延迟 flush 策略保证 content 不被作为中间态发送；V1 继续走现有终结态路径 |
| 多轮 reasoning 迭代，每轮都有中间态 | 每轮 `PhaseEvent("reasoning")` 自然划定边界；前端据此清空旧中间态 |
| 流式调用在发出中间态前失败 | 允许重试整个 reasoning 流 |
| 流式调用在发出中间态后失败 | 不再重试，直接报错，避免重复中间态或重复工具执行 |
| 文本 tool_calls（`<tool_call>` 标签） | 保留 `_parse_textual_tool_calls()` 兜底；可执行，但不把原始 markup content 原样写回 messages 历史 |
| synthesis 阶段的后续 tool_calls | 维持现有逻辑，不引入中间态概念 |

---

## 六、受影响的文件清单

| 文件 | 改动描述 |
|---|---|
| `newbee_notebook/core/engine/stream_events.py` | 新增 `IntermediateContentEvent` 数据类 |
| `newbee_notebook/core/engine/agent_loop.py` | 新增 `_ToolCallAccumulator`、`_StreamReasoningResult`、`_stream_reasoning()`、`_extract_stream_tool_call_deltas()`；修改 reasoning 主循环；调整 assistant tool message 写回策略 |
| `newbee_notebook/application/services/chat_service.py` | `chat_stream()` 中新增 `IntermediateContentEvent` 转发 |

### 原则上无需修改的文件

| 文件 | 原因 |
|---|---|
| `newbee_notebook/api/routers/chat.py` | `sse_adapter()` 的通用透传分支已能处理 `intermediate_content` |
| `newbee_notebook/core/llm/client.py` | `chat_stream()` 接口已存在，底层走 OpenAI 兼容流式接口 |
| `newbee_notebook/core/session/session_manager.py` | 继续透传 agent_loop 事件即可 |
| `newbee_notebook/core/engine/agent_loop.py` 的 `run()` 方法 | 新事件类型会被自然忽略，不影响非流式聚合逻辑 |

---

## 七、测试计划

### 7.1 单元测试

| 测试文件 | 覆盖内容 |
|---|---|
| `tests/unit/core/engine/test_tool_call_accumulator.py` | `_ToolCallAccumulator` 的拼装逻辑：单 tool_call、多 tool_call、空 arguments、分块 name |
| `tests/unit/core/engine/test_stream_reasoning.py` | `_stream_reasoning()` 的行为：content-only 流、structured tool_calls-only 流、content + structured tool_calls 混合流、文本 tool_call fallback、异常重试边界 |
| `tests/unit/core/engine/test_agent_loop_intermediate.py` | `stream()` 主循环在有中间态时正确 yield `IntermediateContentEvent`；无中间态时行为不变 |
| `tests/unit/core/engine/test_agent_loop_textual_tool_calls.py` | 文本型 tool_call 仍可执行，但不会把原始 markup content 回写到 messages 历史 |

### 7.2 契约测试

| 测试文件 | 覆盖内容 |
|---|---|
| `tests/contract/test_sse_intermediate_content.py` | SSE 适配器能输出 `{"type":"intermediate_content","delta":"..."}` |

### 7.3 现有测试兼容

- `tests/unit/core/engine/test_agent_loop.py`：fake `llm_client` 需要同时支持 `chat()` 与 `chat_stream()`。
- `tests/integration/test_chat_engine_integration.py`：需要补 structured tool_call 流式 chunk 的 fake 数据。

---

## 八、与前端的配合边界

| 职责 | 后端 | 前端 |
|---|---|---|
| 流式 reasoning 调用 | `_stream_reasoning()` 负责流式调用和 delta 拼装 | 无需感知 |
| 中间态 content 传递 | 通过 `IntermediateContentEvent` 输出 `intermediate_content` 事件 | 接收并渲染 |
| 生命周期边界 | 继续发出 `phase` 与 `thinking` 事件 | 约定只让 `phase` 负责生命周期清理，`thinking` 负责阶段文字展示 |
| assistant 历史写回 | 仅 structured tool_calls 的自然语言 content 才回写 | 无需感知 |
| 最终回答 | 通过 `ContentEvent` 传递（不变） | 以最终内容替换瞬态中间态 |

---

## 九、待确认事项

1. 当前实际使用的模型供应商在 reasoning 阶段是否稳定返回 structured tool_call delta，已通过探针做了首轮验证：`qwen3.5-plus` 默认不返回中间态 content，`glm-5` 会返回中间态 content，并且流式下先 content 后 tool_call。当前产品默认目标路径按 `glm-5` 设计。详见 `backend/llm-shape-validation.md`。
2. V1 是否接受“无 tool_call 的直接回答”继续保持当前最终态展示，而不额外追求首字流式。如果接受，可以显著降低状态复杂度。
3. 文本型 tool_call fallback 是否只作为兼容兜底，不追求中间态展示。如果要让它也展示中间态，需要先定义 markup 清洗策略。
4. 一旦中间态已经对外发出，后端不再 retry 是否可以接受。这是为了避免重复中间态和重复工具执行，不是技术缺陷，而是幂等性保护。
