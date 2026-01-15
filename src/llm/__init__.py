"""LLM adapters."""

from src.llm.zhipu import build_llm as build_zhipu_llm, ZhipuOpenAI
from src.llm.openai import build_llm as build_openai_llm

__all__ = ["build_zhipu_llm", "build_openai_llm", "ZhipuOpenAI"]
