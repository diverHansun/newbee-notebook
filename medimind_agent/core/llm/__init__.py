"""LLM adapters."""

from medimind_agent.core.llm.zhipu import build_llm as build_zhipu_llm, ZhipuOpenAI
from medimind_agent.core.llm.openai import build_llm as build_openai_llm

__all__ = ["build_zhipu_llm", "build_openai_llm", "ZhipuOpenAI"]


