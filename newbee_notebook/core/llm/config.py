"""Runtime LLM config resolution for the batch-2 client layer."""

from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from newbee_notebook.core.common.config_db import get_llm_config_async

DEFAULT_QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    model: str
    api_key: str
    base_url: str | None
    temperature: float
    max_tokens: int | None
    top_p: float | None

    @property
    def cache_key(self) -> tuple[str, str, str | None, float, int | None, float | None]:
        return (
            self.provider,
            self.model,
            self.base_url,
            self.temperature,
            self.max_tokens,
            self.top_p,
        )


@dataclass(frozen=True)
class LLMRuntimeConfig(ProviderConfig):
    pass


def _resolve_api_key(provider: str) -> str:
    if provider == "qwen":
        return (
            os.getenv("DASHSCOPE_API_KEY")
            or os.getenv("QWEN_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or ""
        )
    if provider == "zhipu":
        return os.getenv("OPENAI_API_KEY") or os.getenv("ZHIPU_API_KEY") or ""
    return os.getenv("OPENAI_API_KEY") or ""


def _resolve_base_url(provider: str) -> str | None:
    if provider == "qwen":
        return (
            os.getenv("QWEN_API_BASE")
            or os.getenv("DASHSCOPE_API_BASE")
            or DEFAULT_QWEN_BASE_URL
        )
    if provider == "zhipu":
        return os.getenv("ZHIPU_API_BASE") or DEFAULT_ZHIPU_BASE_URL
    return os.getenv("OPENAI_API_BASE")


async def resolve_llm_runtime_config(session: AsyncSession) -> LLMRuntimeConfig:
    current = await get_llm_config_async(session)
    provider = str(current["provider"]).strip().lower()
    api_key = _resolve_api_key(provider)
    if not api_key:
        raise ValueError(f"No API key configured for provider: {provider}")

    return LLMRuntimeConfig(
        provider=provider,
        model=str(current["model"]).strip(),
        api_key=api_key,
        base_url=_resolve_base_url(provider),
        temperature=float(current["temperature"]),
        max_tokens=int(current["max_tokens"]) if current.get("max_tokens") is not None else None,
        top_p=float(current["top_p"]) if current.get("top_p") is not None else None,
    )
