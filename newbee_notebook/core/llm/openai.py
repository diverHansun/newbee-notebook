"""OpenAI LLM builder (native OpenAI models).

Reads configuration primarily from environment variables, with optional
overrides from configs/llm.yaml under llm.openai.* if present.
"""

from typing import Optional, Dict, Any
import os

from llama_index.llms.openai import OpenAI

from newbee_notebook.core.common.config import (
    get_llm_config,
)
from newbee_notebook.core.llm.registry import register_llm


def _get_openai_config() -> Dict[str, Any]:
    llm_cfg = get_llm_config().get("llm", {}) if get_llm_config() else {}
    return llm_cfg.get("openai", {})


def _get_api_key() -> Optional[str]:
    return os.getenv("OPENAI_API_KEY")


def _resolve(param: str, default: Any) -> Any:
    cfg = _get_openai_config()
    env_map = {
        "model": "OPENAI_MODEL",
        "temperature": "OPENAI_TEMPERATURE",
        "max_tokens": "OPENAI_MAX_TOKENS",
        "top_p": "OPENAI_TOP_P",
        "api_base": "OPENAI_API_BASE",
        "system_prompt": "OPENAI_SYSTEM_PROMPT",
    }
    env_val = os.getenv(env_map.get(param, ""), None)
    if env_val is not None:
        return type(default)(env_val) if default is not None else env_val
    return cfg.get(param, default)


@register_llm("openai")
def build_llm(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    system_prompt: Optional[str] = None,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
) -> OpenAI:
    """Build and return a native OpenAI LLM instance."""
    final_model = model or _resolve("model", "gpt-4o-mini")
    final_temperature = temperature if temperature is not None else float(_resolve("temperature", 0.2))
    final_max_tokens = max_tokens if max_tokens is not None else _resolve("max_tokens", None)
    final_top_p = top_p if top_p is not None else _resolve("top_p", None)
    final_system_prompt = system_prompt if system_prompt is not None else _resolve("system_prompt", None)

    resolved_api_key = api_key or _get_api_key()
    if not resolved_api_key:
        raise ValueError("OPENAI_API_KEY not set. Please set it in environment or .env file.")

    llm_kwargs: Dict[str, Any] = {
        "model": final_model,
        "temperature": final_temperature,
        "api_key": resolved_api_key,
    }
    if final_max_tokens is not None:
        llm_kwargs["max_tokens"] = final_max_tokens
    if final_top_p is not None:
        llm_kwargs["additional_kwargs"] = {"top_p": final_top_p}
    if api_base or _resolve("api_base", None):
        llm_kwargs["api_base"] = api_base or _resolve("api_base", None)
    if final_system_prompt:
        llm_kwargs["system_prompt"] = final_system_prompt

    # Optional retry/timeout
    cfg = _get_openai_config()
    if "request_timeout" in cfg:
        llm_kwargs["timeout"] = float(cfg["request_timeout"])
    if "max_retries" in cfg:
        llm_kwargs["max_retries"] = int(cfg["max_retries"])

    return OpenAI(**llm_kwargs)


# Backward-compatible naming style
build_openai_llm = build_llm


