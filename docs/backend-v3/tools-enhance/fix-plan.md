# 网络工具兜底与重试机制 - 修改方案

> 基于 `problem-analysis.md` 中的问题分析，本文档描述具体的修改方案。

---

## 1. 修改目标

1. 所有网络工具的错误统一通过 `ToolCallResult.error` 返回，LLM 和前端能正确感知失败
2. 为网络工具增加重试能力，应对临时性网络错误
3. Agent loop 层面增加工具执行异常保护，作为最后一道兜底
4. 不改变工具执行的串行模式，不影响前端 spinner 逻辑

---

## 2. 修改范围

| 文件 | 改动类型 |
|------|---------|
| `core/tools/tavily_tools.py` | 错误处理 + 重试 |
| `core/tools/zhipu_tools.py` | 错误返回修正 + 重试 |
| `core/tools/image_generation.py` | 重试（API 调用阶段） |
| `core/engine/agent_loop.py` | 工具执行异常保护 |

---

## 3. 各模块修改方案

### 3.1 Tavily 工具

**文件**：`newbee_notebook/core/tools/tavily_tools.py`

#### 3.1.1 `_execute` 增加 try/except

为 `build_tavily_search_runtime_tool` 和 `build_tavily_crawl_runtime_tool` 的 `_execute` 增加异常捕获，模式与 `image_generation.py` 对齐：

```python
async def _execute(payload: dict) -> ToolCallResult:
    try:
        return _tavily_runtime_search(...)
    except Exception as exc:
        return ToolCallResult(content="", error=f"web search failed: {exc}")
```

#### 3.1.2 重试逻辑

在 `_execute` 内部包裹重试循环，参数：
- 最大重试次数：2（总共最多 3 次尝试）
- 重试间隔：1s（固定）
- 可重试条件：`requests.exceptions.ConnectionError`、`requests.exceptions.Timeout`、`httpx.TimeoutException`、`httpx.ConnectError`，以及 HTTP 5xx（通过 RuntimeError 消息匹配）
- 不可重试：参数校验错误、API key 缺失（`ValueError`）、4xx 错误

实现方式：

```python
import asyncio

MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 1.0

async def _execute(payload: dict) -> ToolCallResult:
    query = str(payload.get("query") or "").strip()
    if not query:
        return ToolCallResult(content="", error="query is required")

    last_error: Exception | None = None
    for attempt in range(1 + MAX_RETRIES):
        try:
            return _tavily_runtime_search(
                query=query,
                ...
            )
        except Exception as exc:
            if not _is_retryable(exc) or attempt >= MAX_RETRIES:
                return ToolCallResult(content="", error=f"web search failed: {exc}")
            last_error = exc
            await asyncio.sleep(RETRY_DELAY_SECONDS)

    return ToolCallResult(content="", error=f"web search failed after retries: {last_error}")
```

`_is_retryable` 判断函数（定义在文件顶部）：

```python
def _is_retryable(exc: Exception) -> bool:
    import httpx
    if isinstance(exc, (ConnectionError, TimeoutError, httpx.TimeoutException, httpx.ConnectError)):
        return True
    error_msg = str(exc).lower()
    if "http 5" in error_msg or "502" in error_msg or "503" in error_msg or "504" in error_msg:
        return True
    return False
```

#### 3.1.3 Tavily 底层函数保持不变

`tavily_search()` 和 `tavily_crawl()` 的函数签名和行为不变。它们作为同步函数可能被其他地方直接调用，错误处理统一由 `_execute` 层负责。

### 3.2 智谱工具

**文件**：`newbee_notebook/core/tools/zhipu_tools.py`

#### 3.2.1 底层函数改为抛出异常

将 `zhipu_web_search()`（L105-112）和 `zhipu_web_crawl()`（L143-149）中的错误处理从「返回错误字符串」改为「抛出异常」：

修改前（以 `zhipu_web_search` 为例）：

```python
try:
    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    if not resp.ok:
        return f"Zhipu web_search request failed: HTTP {resp.status_code} - {resp.text}"
    data = resp.json()
    return _format_search_results(data)
except Exception as exc:
    return f"Zhipu web_search request error: {exc}"
```

修改后：

```python
resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
if not resp.ok:
    raise ZhipuToolError(f"HTTP {resp.status_code} - {resp.text}")
data = resp.json()
return _format_search_results(data)
```

移除底层函数的 try/except，让异常自然冒泡到 `_execute` 层统一处理。

#### 3.2.2 `_execute` 增加 try/except + 重试

与 Tavily 方案对齐。重试参数相同（2 次重试、1s 间隔）。`_is_retryable` 函数用智谱版本：

```python
def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return True
    if isinstance(exc, ZhipuToolError):
        error_msg = str(exc)
        if any(code in error_msg for code in ("HTTP 5", "502", "503", "504")):
            return True
    return False
```

#### 3.2.3 API key 缺失处理

`_get_api_key()` 抛出的 `ZhipuToolError` 会被 `_execute` 的 try/except 捕获，不会再向上传播。`_is_retryable` 对普通 `ZhipuToolError`（非 5xx）返回 `False`，因此 API key 缺失不会触发重试，直接返回错误。

### 3.3 图片生成工具

**文件**：`newbee_notebook/core/tools/image_generation.py`

#### 3.3.1 仅重试 API 调用阶段

在 `_execute` 内部，对 API 调用部分（`zhipu_generate_image` / `qwen_generate_image`）增加重试，不重试下载和存储阶段。

重试参数：
- 最大重试次数：1（总共最多 2 次尝试）— 图片生成单次耗时长，多次重试会让用户等待过久
- 重试间隔：2s
- 可重试条件：与搜索工具一致（超时、连接错误、5xx）

实现方式：

```python
async def _execute(payload: dict) -> ToolCallResult:
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        return ToolCallResult(content="", error="prompt is required")

    # ... 参数解析 ...

    api_result: ImageAPIResult | None = None
    last_error: Exception | None = None

    for attempt in range(1 + IMAGE_MAX_RETRIES):
        try:
            if provider == "zhipu":
                api_result = await zhipu_generate_image(...)
            else:
                api_result = await qwen_generate_image(...)
            break
        except Exception as exc:
            if not _is_retryable(exc) or attempt >= IMAGE_MAX_RETRIES:
                return ToolCallResult(content="", error=f"image generation failed: {exc}")
            last_error = exc
            await asyncio.sleep(IMAGE_RETRY_DELAY_SECONDS)

    if api_result is None:
        return ToolCallResult(content="", error=f"image generation failed after retries: {last_error}")

    try:
        images = await _save_images(...)
    except Exception as exc:
        return ToolCallResult(content="", error=f"image save failed: {exc}")

    return ToolCallResult(
        content=f"Generated {len(images)} image(s) for prompt: {_safe_preview(prompt)}",
        images=images,
        ...
    )
```

#### 3.3.2 `_is_retryable` 函数

图片生成使用 `requests` 库（通过 `_post_json`），可重试判断：

```python
def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return True
    error_msg = str(exc).lower()
    if "http 5" in error_msg or "502" in error_msg or "503" in error_msg or "504" in error_msg:
        return True
    return False
```

### 3.4 Agent Loop 工具执行异常保护

**文件**：`newbee_notebook/core/engine/agent_loop.py`

#### 3.4.1 主循环工具执行点（L719）

将：

```python
result = await tool.execute(effective_arguments)
```

改为：

```python
try:
    result = await tool.execute(effective_arguments)
except Exception as exc:
    result = ToolCallResult(content="", error=f"tool execution failed: {exc}")
```

后续的 `messages.append`、`yield ToolResultEvent`、`collected_sources.extend` 等逻辑正常执行。由于 `result.error` 不为 `None`，`ToolResultEvent.success` 为 `False`，前端 spinner 会正确显示为 error 状态。

#### 3.4.2 Synthesis 阶段工具执行点（L841）

同样的 try/except 保护，逻辑一致。

#### 3.4.3 行为说明

- 工具异常被捕获后，LLM 会在下一轮对话中看到 `"Error: tool execution failed: ..."` 的 tool result message
- LLM 可以据此决定：换一个工具重试、直接基于已有信息回答、或向用户说明
- **不中断 agent loop 的迭代**，整个对话流保持完整

---

## 4. 重试策略汇总

| 工具类型 | 最大重试次数 | 重试间隔 | 可重试条件 | 不可重试条件 |
|---------|-------------|---------|-----------|-------------|
| Tavily search/crawl | 2 | 1s | 超时、连接错误、5xx | 参数错误、API key 缺失、4xx |
| 智谱 search/crawl | 2 | 1s | 超时、连接错误、5xx | 参数错误、API key 缺失、4xx |
| 图片生成 (zhipu/qwen) | 1 | 2s | 超时、连接错误、5xx | 参数错误、API key 缺失、4xx |

---

## 5. 不做的事

1. **不引入外部重试库**（tenacity/backoff）— 当前只有 3 个网络工具，各自内联重试即可
2. **不抽取公共重试工具函数** — 三个工具的重试场景接近但不完全相同（图片生成需要分离 API 调用和存储阶段），过早抽象反而增加耦合
3. **不改造并发执行** — 前端 spinner 为单任务展示模型，并发会导致显示异常
4. **不修改 `knowledge_base` 工具** — 该工具依赖本地 ES/PGVector，不属于外部网络 API 调用，其连接稳定性由基础设施层保障；agent loop 的兜底 try/except 已覆盖其异常场景
5. **不把重试参数放到 yaml 配置** — 当前场景简单，硬编码常量足够；如未来工具增多再考虑配置化

---

## 6. 验证要点

1. Tavily search/crawl 在网络异常时返回 `ToolCallResult.error`，不抛出未处理异常
2. 智谱 search/crawl 在网络异常时返回 `ToolCallResult.error`，不再将错误字符串作为 content
3. 图片生成在 API 调用临时失败时自动重试一次，最终失败时返回 `ToolCallResult.error`
4. Agent loop 在任何工具抛出异常时不中断 `stream()`，正常 yield `ToolResultEvent(success=False)`
5. 前端 spinner 在工具失败时正确显示 error 状态（不卡在 running）
