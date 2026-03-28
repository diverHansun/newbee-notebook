"""Zhipu embedding builder via the official embeddings HTTP API.

This preserves the existing ``zhipu`` provider name for runtime/config
compatibility without depending on the dedicated ``zhipuai`` SDK.
"""

from __future__ import annotations

from typing import Any, Dict, List
import os

from llama_index.embeddings.openai import OpenAIEmbedding

from newbee_notebook.core.common.config import get_embeddings_config, get_zhipu_api_key
from newbee_notebook.core.rag.embeddings.base import BaseEmbeddingModel
from newbee_notebook.core.rag.embeddings.registry import register_embedding

DEFAULT_ZHIPU_EMBEDDINGS_BASE = "https://open.bigmodel.cn/api/paas/v4"


class ZhipuEmbeddingWrapper(BaseEmbeddingModel):
    """Wrapper for OpenAI-compatible Zhipu embeddings."""

    def __init__(self, embedding_client: OpenAIEmbedding, model_name: str):
        super().__init__(model_name=model_name)
        self._embedding_client = embedding_client

    @property
    def dimensions(self) -> int:
        return self._embedding_client.dimensions

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._embedding_client._get_query_embedding(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._embedding_client._get_text_embedding(text)

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self._embedding_client._get_text_embeddings(texts)

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return await self._embedding_client._aget_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return await self._embedding_client._aget_text_embedding(text)

    async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return await self._embedding_client._aget_text_embeddings(texts)


def _get_zhipu_config() -> Dict[str, Any]:
    embeddings_config = get_embeddings_config()
    return embeddings_config.get("embeddings", {}).get("zhipu", {})


def _get_api_base(config: Dict[str, Any]) -> str:
    return (
        os.getenv("ZHIPU_API_BASE")
        or os.getenv("EMBEDDING_API_BASE")
        or config.get("api_base")
        or DEFAULT_ZHIPU_EMBEDDINGS_BASE
    )


@register_embedding("zhipu")
def build_zhipu_embedding(
    model: str | None = None,
    dimensions: int | None = None,
) -> BaseEmbeddingModel:
    """Build a Zhipu embedding client against the official embeddings API."""
    api_key = get_zhipu_api_key()
    if not api_key:
        raise ValueError(
            "ZHIPU_API_KEY not set. Please set it in environment variables or .env file"
        )

    config = _get_zhipu_config()
    final_model = model or os.getenv("EMBEDDING_MODEL") or config.get("model", "embedding-3")
    final_dimensions = int(
        dimensions or os.getenv("EMBEDDING_DIMENSION") or config.get("dim", 1024)
    )

    embedding_client = OpenAIEmbedding(
        model=final_model,
        api_key=api_key,
        api_base=_get_api_base(config),
        dimensions=final_dimensions,
    )

    return ZhipuEmbeddingWrapper(
        embedding_client=embedding_client,
        model_name=f"zhipu-{final_model}",
    )


# Backward compatibility export expected by some tests
build_embedding = build_zhipu_embedding
