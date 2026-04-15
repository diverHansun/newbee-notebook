# 网络工具兜底与重试机制 - 问题分析

> 本文档仅用于问题说明与根因分析，不包含具体代码改造步骤。

---

## 1. 问题概述

Agent 运行时可调用的内置工具中，有多个依赖外部 API + 网络请求。当前这些工具在面对网络超时、服务端错误、API 限流等场景时，缺乏统一的错误处理和重试能力，轻则向用户展示不友好的错误信息，重则导致整个对话流中断。

涉及的网络工具：

| 工具名 | 文件 | 依赖外部服务 |
|--------|------|-------------|
| `tavily_search` | `core/tools/tavily_tools.py` | Tavily Search API |
| `tavily_crawl` | `core/tools/tavily_tools.py` | Tavily Crawl API |
| `zhipu_web_search` | `core/tools/zhipu_tools.py` | 智谱 Web Search API |
| `zhipu_web_crawl` | `core/tools/zhipu_tools.py` | 智谱 Web Reader API |
| `image_generate` | `core/tools/image_generation.py` | 智谱 GLM-Image / 通义 Qwen-Image API |

---

## 2. 逐模块问题分析

### 2.1 Tavily 搜索与爬取工具

**文件**：`newbee_notebook/core/tools/tavily_tools.py`

#### 问题 A：`_execute` 无异常捕获

`build_tavily_search_runtime_tool` 的 `_execute`（L158-165）和 `build_tavily_crawl_runtime_tool` 的 `_execute`（L211-216）直接调用底层函数，无 try/except：

```python
async def _execute(payload: dict) -> ToolCallResult:
    return _tavily_runtime_search(
        query=str(payload.get("query") or "").strip(),
        ...
    )
```

`_tavily_runtime_search` 内部调用 `tavily_search()` → `TavilyClient.search()`，Tavily SDK 在以下场景会抛出异常：
- 网络连接超时或中断
- API 返回 4xx/5xx
- API key 无效或过期
- 速率限制

这些异常会直接从 `_execute` 向上传播，未被转换为 `ToolCallResult.error`。

#### 问题 B：无 timeout 配置

`TavilyClient` 在构造时未传入 timeout 参数（L40）：

```python
client = TavilyClient(api_key=_require_api_key())
```

如果 Tavily 服务端无响应，请求将使用 SDK 的默认超时（取决于 httpx 默认值），无法保证可控的等待时间。

#### 问题 C：API key 缺失直接抛异常

`_require_api_key()`（L11-15）在环境变量未配置时抛出 `ValueError`，该异常在 `_execute` 层面未被捕获。

### 2.2 智谱搜索与爬取工具

**文件**：`newbee_notebook/core/tools/zhipu_tools.py`

#### 问题 A：错误被当作正常内容返回

底层函数 `zhipu_web_search()`（L105-112）和 `zhipu_web_crawl()`（L143-149）有 try/except，但将错误以字符串形式作为正常内容返回：

```python
try:
    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    if not resp.ok:
        return f"Zhipu web_search request failed: HTTP {resp.status_code} - {resp.text}"
    ...
except Exception as exc:
    return f"Zhipu web_search request error: {exc}"
```

上层 `_zhipu_runtime_search` 再将其封装为 `ToolCallResult(content=content)`，此时 `error` 字段为 `None`。

后果：
- Agent loop 无法感知工具调用失败（`result.error is None`）
- LLM 可能将错误字符串（如 `"Zhipu web_search request error: ConnectionTimeout"`）当作搜索结果引用到回答中
- 前端 `ToolResultEvent` 的 `success` 字段始终为 `True`，spinner 状态不正确

#### 问题 B：API key 缺失异常未捕获

`_get_api_key()`（L21-24）在环境变量未设置时抛出 `ZhipuToolError`，但 `_execute` wrapper（L210-213、L245-248）没有 try/except 包裹。该异常会向上传播。

#### 已有优势

- 底层 HTTP 请求有 timeout 配置（从 `zhipu_tools.yaml` 读取，默认 30s）
- HTTP 异常不会导致进程崩溃（仅返回错误字符串）

### 2.3 图片生成工具

**文件**：`newbee_notebook/core/tools/image_generation.py`

#### 已有优势

`_execute`（L369-394）已正确包裹 try/except，并通过 `ToolCallResult.error` 返回错误信息：

```python
except Exception as exc:
    return ToolCallResult(content="", error=f"image generation failed: {exc}")
```

同时有明确的 timeout（`DEFAULT_REQUEST_TIMEOUT_SECONDS = 90s`，L29）。

#### 问题：无重试机制

图片生成 API 调用耗时通常在 10-60s，期间受网络波动影响概率较高。当前实现在遇到临时性错误（如 502/503、连接超时）时直接返回失败，没有重试机会。

`zhipu_generate_image()`（L202-229）和 `qwen_generate_image()`（L232-269）均通过 `asyncio.to_thread(_post_json, ...)` 发起请求，`_post_json`（L144-148）在 HTTP 非 200 时直接抛出 `RuntimeError`，不区分可重试错误和不可重试错误。

### 2.4 Agent Loop 工具执行层

**文件**：`newbee_notebook/core/engine/agent_loop.py`

#### 问题：工具执行无异常保护

主循环的工具执行点（L719）和 synthesis 阶段的工具执行点（L841）均无 try/except：

```python
result = await tool.execute(effective_arguments)
```

如果任何工具的 `_execute` 抛出未处理的异常，该异常会直接从 `stream()` async generator 中冒泡出去。调用方（`chat_service` 等）收到的是未捕获的异常而非优雅的 `ErrorEvent`，导致：
- SSE 流意外中断
- 前端显示连接断开而非工具失败
- 后续的工具调用和 synthesis 阶段无法执行

此处是所有工具异常的最后一道防线。即使各工具自身做好了 try/except，agent loop 层面也应有兜底保护。

---

## 3. 错误处理模式对比

| 维度 | Tavily | 智谱 | 图片生成 |
|------|--------|------|---------|
| `_execute` 有 try/except | 无 | 无 | 有 |
| 底层函数有 try/except | 无 | 有（但返回方式不正确） | 有（通过上层捕获） |
| 使用 `ToolCallResult.error` | 仅参数校验 | 仅参数校验 | 正确使用 |
| 有 timeout 配置 | 无 | 有（30s，来自 yaml） | 有（90s，硬编码常量） |
| 有重试机制 | 无 | 无 | 无 |
| API key 缺失处理 | 抛 ValueError | 抛 ZhipuToolError | 由上游 context 注入 |

---

## 4. 前端影响分析

### 4.1 Spinner 状态显示

前端 `ToolStepsIndicator`（`frontend/src/components/chat/message-item.tsx` L101-127）只展示 `toolSteps` 数组最后一个元素：

```tsx
const latestStep = steps[steps.length - 1];
```

工具执行成功/失败的状态由 SSE 的 `tool_result` 事件驱动（`useChatSession.ts` L1079-1088）：

```tsx
updateToolStepInSession(sessionId, id, event.tool_call_id, event.success ? "done" : "error");
```

当前如果工具在 agent loop 层面异常崩溃，`tool_result` 事件不会被发出，导致 spinner 停留在 `"running"` 状态，直到 SSE 连接断开。

### 4.2 并发执行对 spinner 的影响

当前 spinner 是单任务展示模型（只显示最后一个 step），如果未来改为并发执行多个工具调用，会出现：
- 多个 `tool_call` 事件几乎同时发出，label 闪烁覆盖
- `tool_result` 到达顺序不可控，最终状态可能具有误导性

因此本次不改造为并发执行，保持串行。

---

## 5. 影响范围

1. **受影响模块**：agent 模式和 chat 模式下所有网络工具调用链路
2. **受影响用户**：使用网络搜索、网页爬取、图片生成功能的用户
3. **用户侧表现**：对话中断、spinner 卡死、错误信息被当作回答内容引用
4. **系统侧表现**：SSE 流异常断开、未捕获异常出现在服务端日志

---

## 6. 分析结论

本次问题涉及三个层面：

1. **工具层面**：Tavily 工具完全缺乏错误处理；智谱工具的错误处理模式不正确（错误被当作正常内容）；所有网络工具缺乏重试能力。
2. **Agent loop 层面**：工具执行点没有异常保护，是系统脆弱性的最后一道未设防的关口。
3. **一致性层面**：三类网络工具的错误处理方式互不统一，图片生成的模式（try/except + `ToolCallResult.error`）是正确的参考标准。
