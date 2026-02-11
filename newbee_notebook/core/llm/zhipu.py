"""Zhipu models via OpenAI-compatible interface.

This wraps llama-index's OpenAI adapter but targets Zhipu's OpenAI-compatible
endpoint, keeping the config shape of llm.yaml (zhipu section).
"""

from typing import Optional, Dict, Any
import os

from llama_index.llms.openai import OpenAI
from llama_index.llms.openai.utils import (
    openai_modelname_to_contextsize,
    is_chat_model,
    is_function_calling_model,
)
from llama_index.core.base.llms.types import LLMMetadata, MessageRole

from newbee_notebook.core.common.config import (
    get_llm_config,
    get_llm_model,
    get_llm_temperature,
    get_llm_max_tokens,
    get_llm_top_p,
    get_llm_system_prompt,
    get_zhipu_api_key,
)

# Zhipu's OpenAI-compatible endpoint
DEFAULT_ZHIPU_OPENAI_BASE = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_CONTEXT_WINDOW = 128000  # glm-4-plus rough limit


def _get_api_key() -> Optional[str]:
    """Get API key, preferring OpenAI key but falling back to Zhipu."""
    return os.getenv("OPENAI_API_KEY") or get_zhipu_api_key()


def _get_api_base() -> str:
    """Resolve API base URL with sensible defaults for Zhipu OpenAI compatibility."""
    llm_cfg = get_llm_config().get("llm", {}).get("zhipu", {}) if get_llm_config() else {}
    return (
        os.getenv("OPENAI_API_BASE")
        or os.getenv("LLM_API_BASE")
        or os.getenv("ZHIPU_API_BASE")
        or llm_cfg.get("api_base")
        or DEFAULT_ZHIPU_OPENAI_BASE
    )


def _get_timeout_and_retries() -> tuple[float, int]:
    """Read timeout and max_retries from llm.yaml if provided."""
    llm_cfg = get_llm_config().get("llm", {}).get("zhipu", {}) if get_llm_config() else {}
    timeout = float(llm_cfg.get("request_timeout", 60.0))
    max_retries = int(llm_cfg.get("max_retries", 3))
    return timeout, max_retries


class ZhipuOpenAI(OpenAI):
    """OpenAI-compatible LLM with graceful fallback for non-OpenAI model names."""

    @property
    def metadata(self) -> LLMMetadata:
        """Return metadata without rejecting unknown model names."""
        model_name = self._get_model_name()
        try:
            context_window = openai_modelname_to_contextsize(model_name)
            chat_model = is_chat_model(model=model_name)
            fn_model = is_function_calling_model(model_name)
        except Exception:
            context_window = DEFAULT_CONTEXT_WINDOW
            chat_model = True
            fn_model = True

        return LLMMetadata(
            context_window=context_window,
            num_output=self.max_tokens or -1,
            is_chat_model=chat_model,
            is_function_calling_model=fn_model,
            model_name=self.model,
            system_role=MessageRole.SYSTEM,
        )

    @property
    def _tokenizer(self):
        """Avoid tiktoken errors on custom model names."""
        try:
            return super()._tokenizer
        except Exception:
            return None


def build_llm(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    system_prompt: Optional[str] = None,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
) -> OpenAI:
    """Build and return an OpenAI-compatible LLM targeting Zhipu models."""
    final_model = model if model is not None else get_llm_model()
    final_temperature = temperature if temperature is not None else get_llm_temperature()
    final_max_tokens = max_tokens if max_tokens is not None else get_llm_max_tokens()
    final_top_p = top_p if top_p is not None else get_llm_top_p()
    final_system_prompt = system_prompt if system_prompt is not None else get_llm_system_prompt()

    resolved_api_key = api_key or _get_api_key()
    if not resolved_api_key:
        raise ValueError(
            "API key not set. Please set OPENAI_API_KEY or ZHIPU_API_KEY in your environment or .env file."
        )

    timeout, max_retries = _get_timeout_and_retries()

    additional_kwargs: Dict[str, Any] = {}
    if final_top_p is not None:
        additional_kwargs["top_p"] = final_top_p

    llm_kwargs: Dict[str, Any] = {
        "model": final_model,
        "temperature": final_temperature,
        "max_tokens": final_max_tokens,
        "api_key": resolved_api_key,
        "api_base": api_base or _get_api_base(),
        "timeout": timeout,
        "max_retries": max_retries,
    }

    if final_system_prompt:
        llm_kwargs["system_prompt"] = final_system_prompt

    if additional_kwargs:
        llm_kwargs["additional_kwargs"] = additional_kwargs

    return ZhipuOpenAI(**llm_kwargs)


