"""LLM adapters with registry-based provider selection."""

from newbee_notebook.core.common.config import get_llm_provider
from newbee_notebook.core.llm.client import LLMClient
from newbee_notebook.core.llm.config import LLMRuntimeConfig, ProviderConfig
from newbee_notebook.core.llm.factory import LLMClientFactory
from newbee_notebook.core.llm.registry import get_builder, get_registered_providers

# Import provider modules to trigger @register_llm decorators.
from newbee_notebook.core.llm import zhipu as _zhipu  # noqa: F401
from newbee_notebook.core.llm import openai as _openai  # noqa: F401
from newbee_notebook.core.llm import qwen as _qwen  # noqa: F401

from newbee_notebook.core.llm.zhipu import ZhipuOpenAI, build_zhipu_llm
from newbee_notebook.core.llm.openai import build_openai_llm
from newbee_notebook.core.llm.qwen import QwenOpenAI, build_qwen_llm


def build_llm():
    """Build LLM from llm.provider config or LLM_PROVIDER environment override."""
    provider = get_llm_provider()
    builder = get_builder(provider)
    return builder()


__all__ = [
    "build_llm",
    "LLMClient",
    "LLMRuntimeConfig",
    "ProviderConfig",
    "LLMClientFactory",
    "build_zhipu_llm",
    "build_openai_llm",
    "build_qwen_llm",
    "get_registered_providers",
    "ZhipuOpenAI",
    "QwenOpenAI",
]


