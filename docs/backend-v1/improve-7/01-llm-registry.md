# LLM Registry Pattern 与 Qwen 供应商接入

本文档描述 LLM 模块的 Registry Pattern 改造方案，以及阿里云百炼 Qwen 系列模型的接入设计。

---

## 1. 现状分析

### 1.1 当前 LLM 模块结构

```
core/llm/
├── __init__.py     # 直接 import build_zhipu_llm, build_openai_llm
├── zhipu.py        # ZhipuOpenAI(OpenAI) + build_llm()
└── openai.py       # build_llm() → OpenAI(...)
```

**当前问题**:

- 没有统一的 provider 选择机制，上层代码需要手动 import 特定供应商的 `build_llm`
- `llm.yaml` 中没有 `provider` 字段，无法通过配置切换
- 新增供应商需要修改 `__init__.py` 和调用方代码，违反开闭原则 (OCP)
- 与 Embedding 模块的 Registry Pattern 架构不一致

### 1.2 对比: Embedding 模块已有的 Registry Pattern

```python
# Embedding 模块的模式 (已实现)
@register_embedding("biobert")
def build_biobert_embedding() -> BaseEmbeddingModel: ...

@register_embedding("zhipu")
def build_zhipu_embedding() -> BaseEmbeddingModel: ...

# 统一工厂
embed_model = build_embedding()  # 自动读 yaml provider 字段
```

LLM 模块需要采用相同模式。

---

## 2. Registry Pattern 设计

### 2.1 目标架构

```
core/llm/
├── base.py         # 新增: BaseLLM 类型别名 + 配置接口
├── registry.py     # 新增: @register_llm 装饰器 + 工厂
├── zhipu.py        # 改造: @register_llm("zhipu")
├── qwen.py         # 新增: @register_llm("qwen")
├── openai.py       # 改造: @register_llm("openai")
└── __init__.py     # 改造: build_llm() 走 registry
```

### 2.2 LLM Registry

```python
# core/llm/registry.py

"""LLM provider registry for dynamic provider management.

与 Embedding 模块的 registry.py 遵循相同的设计模式。
"""

from typing import Callable, Dict, List
from llama_index.core.llms import LLM


# Global registry for LLM providers
_LLM_REGISTRY: Dict[str, Callable[[], LLM]] = {}


def register_llm(name: str):
    """Decorator for registering LLM provider builders.

    Args:
        name: Provider name (e.g., 'zhipu', 'qwen', 'openai')

    Example:
        >>> @register_llm("qwen")
        ... def build_qwen_llm() -> LLM:
        ...     return QwenOpenAI(...)
    """
    def decorator(builder_func: Callable[[], LLM]):
        if name in _LLM_REGISTRY:
            raise ValueError(
                f"LLM provider '{name}' is already registered."
            )
        _LLM_REGISTRY[name] = builder_func
        return builder_func
    return decorator


def get_registered_providers() -> List[str]:
    """Get list of all registered LLM providers."""
    return sorted(_LLM_REGISTRY.keys())


def get_builder(provider: str) -> Callable[[], LLM]:
    """Get builder function for specified provider."""
    if provider not in _LLM_REGISTRY:
        available = get_registered_providers()
        raise ValueError(
            f"Unknown LLM provider: '{provider}'. "
            f"Available providers: {available}. "
            f"Please check configs/llm.yaml or ensure the provider module is imported."
        )
    return _LLM_REGISTRY[provider]
```

### 2.3 统一工厂函数

```python
# core/llm/__init__.py (改造后)

"""LLM adapters with registry-based provider selection."""

from newbee_notebook.core.common.config import get_llm_provider
from newbee_notebook.core.llm.registry import get_builder, get_registered_providers

# Import provider modules to trigger @register_llm decorators
from newbee_notebook.core.llm import zhipu   # noqa: F401
from newbee_notebook.core.llm import qwen    # noqa: F401
from newbee_notebook.core.llm import openai  # noqa: F401


def build_llm() -> "LLM":
    """Build LLM based on llm.yaml provider field.

    与 build_embedding() 遵循相同的工厂模式。
    """
    provider = get_llm_provider()
    builder = get_builder(provider)
    return builder()


__all__ = ["build_llm", "get_registered_providers"]
```

### 2.4 配置读取

需要在 `core/common/config.py` 中新增:

```python
def get_llm_provider() -> str:
    """Read LLM provider from llm.yaml or environment variable.

    优先级: LLM_PROVIDER 环境变量 > llm.yaml provider 字段 > 默认 'zhipu'
    """
    env_provider = os.getenv("LLM_PROVIDER")
    if env_provider:
        return env_provider.lower()

    llm_cfg = get_llm_config()
    if llm_cfg:
        return llm_cfg.get("llm", {}).get("provider", "zhipu")
    return "zhipu"
```

---

## 3. llm.yaml 改造

### 3.1 新增 provider 字段

```yaml
# configs/llm.yaml

llm:
  # Provider selection: 'zhipu', 'qwen', 'openai'
  # 可通过环境变量 LLM_PROVIDER 覆盖
  provider: zhipu

  # ---- ZhipuAI GLM 系列 ----
  zhipu:
    model: glm-4-plus
    api_base: https://open.bigmodel.cn/api/paas/v4
    temperature: 0.7
    max_tokens: 8192
    top_p: 0.8
    request_timeout: 60.0
    max_retries: 3
    streaming: true
    system_prompt: >-
      Your name is newbee-notebook.
      You are a professional assistant.
      Provide accurate, evidence-based information.

  # ---- 阿里云百炼 Qwen 系列 ---- (新增)
  qwen:
    model: qwen-plus                  # 可选: qwen3-max, qwen-plus, qwen-turbo, qwen-max, qwen-long
    api_base: https://dashscope.aliyuncs.com/compatible-mode/v1
    temperature: 0.7
    max_tokens: 8192
    top_p: 0.8
    request_timeout: 60.0
    max_retries: 3
    streaming: true
    enable_search: false              # Qwen 特有: 联网搜索
    enable_thinking: false            # Qwen 特有: 深度思考
    system_prompt: >-
      Your name is newbee-notebook.
      You are a professional assistant.
      Provide accurate, evidence-based information.

  # ---- OpenAI 原生 ----
  openai:
    model: gpt-4o-mini
    # api_base: (默认 OpenAI 官方)
    temperature: 0.2
    request_timeout: 60.0
    max_retries: 3
```

### 3.2 向后兼容

改造后原有的 `build_zhipu_llm()` 和 `build_openai_llm()` 函数仍保留，作为直接调用的后备入口。新增的 `build_llm()` 统一入口走 registry。

---

## 4. QwenOpenAI 实现

### 4.1 设计思路

Qwen 的 DashScope API 完全兼容 OpenAI 协议，实现方式与 `ZhipuOpenAI` 高度一致:

- 继承 LlamaIndex 的 `OpenAI` 类
- 覆写 `metadata` 属性处理非 OpenAI 标准模型名
- 覆写 `_tokenizer` 属性避免 tiktoken 报错
- 通过 `api_base` 指向 DashScope endpoint

### 4.2 实现代码

```python
# core/llm/qwen.py

"""Qwen models via Alibaba Cloud DashScope OpenAI-compatible interface.

接入阿里云百炼 Qwen 系列模型，通过 OpenAI 兼容端点调用。
支持: qwen3-max, qwen-plus, qwen-turbo, qwen-max, qwen-long 等全系列模型。
"""

from typing import Optional, Dict, Any
import os

from llama_index.llms.openai import OpenAI
from llama_index.core.base.llms.types import LLMMetadata, MessageRole

from newbee_notebook.core.common.config import get_llm_config
from newbee_notebook.core.llm.registry import register_llm

# DashScope OpenAI-compatible endpoint
DEFAULT_DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# Qwen model context windows
QWEN_CONTEXT_WINDOWS = {
    "qwen3-max": 262144,
    "qwen-plus": 1000000,
    "qwen-turbo": 1000000,
    "qwen-max": 32768,
    "qwen-max-latest": 131072,
    "qwen-long": 10000000,
    "qwen3-max-preview": 262144,
}
DEFAULT_CONTEXT_WINDOW = 131072


def _get_qwen_config() -> Dict[str, Any]:
    llm_cfg = get_llm_config()
    if not llm_cfg:
        return {}
    return llm_cfg.get("llm", {}).get("qwen", {})


def _get_api_key() -> Optional[str]:
    """Get DashScope API key from environment."""
    return (
        os.getenv("DASHSCOPE_API_KEY")
        or os.getenv("QWEN_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )


class QwenOpenAI(OpenAI):
    """OpenAI-compatible LLM targeting Alibaba Cloud DashScope.

    与 ZhipuOpenAI 遵循相同的设计模式:
    - 继承 LlamaIndex OpenAI 类
    - 覆写 metadata 处理 Qwen 模型名
    - 覆写 _tokenizer 避免 tiktoken 报错
    """

    @property
    def metadata(self) -> LLMMetadata:
        model_name = self._get_model_name()
        context_window = QWEN_CONTEXT_WINDOWS.get(
            model_name, DEFAULT_CONTEXT_WINDOW
        )
        return LLMMetadata(
            context_window=context_window,
            num_output=self.max_tokens or -1,
            is_chat_model=True,
            is_function_calling_model=True,
            model_name=self.model,
            system_role=MessageRole.SYSTEM,
        )

    @property
    def _tokenizer(self):
        """Avoid tiktoken errors on Qwen model names."""
        try:
            return super()._tokenizer
        except Exception:
            return None


@register_llm("qwen")
def build_qwen_llm(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    system_prompt: Optional[str] = None,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
) -> OpenAI:
    """Build and return an OpenAI-compatible LLM targeting Qwen models."""
    cfg = _get_qwen_config()

    final_model = model or cfg.get("model", "qwen-plus")
    final_temperature = temperature if temperature is not None else cfg.get("temperature", 0.7)
    final_max_tokens = max_tokens if max_tokens is not None else cfg.get("max_tokens", 8192)
    final_top_p = top_p if top_p is not None else cfg.get("top_p", 0.8)
    final_system_prompt = system_prompt or cfg.get("system_prompt", "")

    resolved_api_key = api_key or _get_api_key()
    if not resolved_api_key:
        raise ValueError(
            "DashScope API key not set. "
            "Please set DASHSCOPE_API_KEY or QWEN_API_KEY in your environment or .env file."
        )

    timeout = float(cfg.get("request_timeout", 60.0))
    max_retries = int(cfg.get("max_retries", 3))

    additional_kwargs: Dict[str, Any] = {}
    if final_top_p is not None:
        additional_kwargs["top_p"] = final_top_p

    # Qwen 特有参数
    if cfg.get("enable_search"):
        additional_kwargs["enable_search"] = True
    if cfg.get("enable_thinking"):
        additional_kwargs["enable_thinking"] = True

    llm_kwargs: Dict[str, Any] = {
        "model": final_model,
        "temperature": final_temperature,
        "max_tokens": final_max_tokens,
        "api_key": resolved_api_key,
        "api_base": api_base or cfg.get("api_base", DEFAULT_DASHSCOPE_BASE),
        "timeout": timeout,
        "max_retries": max_retries,
    }

    if final_system_prompt:
        llm_kwargs["system_prompt"] = final_system_prompt
    if additional_kwargs:
        llm_kwargs["additional_kwargs"] = additional_kwargs

    return QwenOpenAI(**llm_kwargs)
```

### 4.3 与 ZhipuOpenAI 的对比

| 要素 | ZhipuOpenAI | QwenOpenAI |
|------|------------|-----------|
| 基类 | `OpenAI` (LlamaIndex) | `OpenAI` (LlamaIndex) |
| API 端点 | `open.bigmodel.cn/api/paas/v4` | `dashscope.aliyuncs.com/compatible-mode/v1` |
| API Key 环境变量 | `ZHIPU_API_KEY` | `DASHSCOPE_API_KEY` |
| metadata 覆写 | 是 (fallback 128K) | 是 (查表 + fallback 131K) |
| tokenizer 覆写 | 是 | 是 |
| 流式输出 | `stream: true` 原生支持 | `stream: true` 原生支持 |
| Function Calling | 支持 | 支持 |
| 特有参数 | 无 | `enable_search`, `enable_thinking` |

---

## 5. 流式输出支持

### 5.1 当前流式架构

项目已在所有对话模式中实现了流式输出:

```
ChatRouter (SSE)
    |
    v
ChatService.stream_chat()
    |
    v
SessionManager.stream()
    |
    v
ModeEngine.stream()          # chat_mode / ask_mode / explain_mode / conclude_mode
    |
    v
LlamaIndex astream_chat()    # LLM 层的流式调用
    |
    v
OpenAI SDK (stream=True)     # HTTP 层的 SSE 流
```

### 5.2 Qwen 流式输出兼容性

LlamaIndex 的 `OpenAI` 类在 `astream_chat()` 中自动设置 `stream=True`，DashScope 的 OpenAI 兼容 API 对此参数的响应格式与 OpenAI 标准一致:

```
data: {"choices":[{"delta":{"content":"你"},"index":0}],"model":"qwen-plus"}
data: {"choices":[{"delta":{"content":"好"},"index":0}],"model":"qwen-plus"}
...
data: [DONE]
```

因此 **Qwen 的流式输出无需额外代码，LlamaIndex + OpenAI 兼容模式自动生效**。

### 5.3 Qwen 特有的流式扩展

DashScope 支持 `stream_options: {"include_usage": true}`，在流的最后一个 chunk 中返回 token 用量统计。如需启用，可在 `additional_kwargs` 中传入。当前阶段不作为必需功能。

---

## 6. zhipu.py 改造

现有 `zhipu.py` 只需添加 `@register_llm("zhipu")` 装饰器:

```python
# zhipu.py 改造点 (最小改动)

from newbee_notebook.core.llm.registry import register_llm

# ... 现有代码不变 ...

@register_llm("zhipu")      # 新增这一行
def build_llm(
    model: Optional[str] = None,
    ...
) -> OpenAI:
    """Build and return an OpenAI-compatible LLM targeting Zhipu models."""
    # ... 现有逻辑不变 ...
```

`openai.py` 同理添加 `@register_llm("openai")`。

---

## 7. 需要新增/修改的文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `core/llm/registry.py` | 新增 | LLM Provider Registry |
| `core/llm/qwen.py` | 新增 | QwenOpenAI + build_qwen_llm |
| `core/llm/__init__.py` | 修改 | 统一 build_llm() 走 registry |
| `core/llm/zhipu.py` | 修改 | 添加 @register_llm("zhipu") |
| `core/llm/openai.py` | 修改 | 添加 @register_llm("openai") |
| `core/common/config.py` | 修改 | 新增 get_llm_provider() |
| `configs/llm.yaml` | 修改 | 新增 provider 字段、qwen section |
| `.env.example` | 修改 | 新增 DASHSCOPE_API_KEY 说明 |
