"""Qwen models via OpenAI-compatible DashScope interface."""

from typing import Optional, Dict, Any
import os

from llama_index.llms.openai import OpenAI
from llama_index.core.base.llms.types import LLMMetadata, MessageRole

from newbee_notebook.core.common.config import get_llm_config
from newbee_notebook.core.llm.registry import register_llm


DEFAULT_DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_CONTEXT_WINDOW = 131072
QWEN_CONTEXT_WINDOWS = {
    "qwen3-max": 262144,
    "qwen-plus": 1000000,
    "qwen-turbo": 1000000,
    "qwen-max": 32768,
    "qwen-max-latest": 131072,
    "qwen-long": 10000000,
    "qwen3-max-preview": 262144,
}


def _get_qwen_config() -> Dict[str, Any]:
    llm_cfg = get_llm_config()
    if not llm_cfg:
        return {}
    return llm_cfg.get("llm", {}).get("qwen", {})


def _get_api_key() -> Optional[str]:
    return (
        os.getenv("DASHSCOPE_API_KEY")
        or os.getenv("QWEN_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )


def _env_or_none(name: str) -> Optional[str]:
    raw = os.getenv(name)
    if raw is None:
        return None
    value = raw.strip()
    return value if value else None


def _env_float(name: str, default: float) -> float:
    raw = _env_or_none(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = _env_or_none(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class QwenOpenAI(OpenAI):
    """OpenAI-compatible LLM adapter targeting DashScope."""

    @property
    def metadata(self) -> LLMMetadata:
        model_name = self._get_model_name()
        context_window = QWEN_CONTEXT_WINDOWS.get(model_name, DEFAULT_CONTEXT_WINDOW)
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
        # DashScope model names are not always recognized by tiktoken.
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
    """Build and return a Qwen LLM via DashScope OpenAI-compatible endpoint."""
    cfg = _get_qwen_config()

    final_model = model or _env_or_none("LLM_MODEL") or cfg.get("model", "qwen3.5-plus")
    final_temperature = (
        temperature
        if temperature is not None
        else _env_float("LLM_TEMPERATURE", float(cfg.get("temperature", 0.7)))
    )
    final_max_tokens = (
        max_tokens
        if max_tokens is not None
        else _env_int("LLM_MAX_TOKENS", int(cfg.get("max_tokens", 32768)))
    )
    final_top_p = (
        top_p
        if top_p is not None
        else _env_float("LLM_TOP_P", float(cfg.get("top_p", 0.8)))
    )
    final_system_prompt = (
        system_prompt
        or _env_or_none("LLM_SYSTEM_PROMPT")
        or cfg.get("system_prompt", "")
    )

    resolved_api_key = api_key or _get_api_key()
    if not resolved_api_key:
        raise ValueError(
            "DashScope API key not set. Please set DASHSCOPE_API_KEY (recommended) "
            "or QWEN_API_KEY in your environment or .env file."
        )

    timeout = float(cfg.get("request_timeout", 60.0))
    max_retries = int(cfg.get("max_retries", 3))

    additional_kwargs: Dict[str, Any] = {}
    if final_top_p is not None:
        additional_kwargs["top_p"] = final_top_p
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


# Backward-compatible naming style
build_llm = build_qwen_llm
