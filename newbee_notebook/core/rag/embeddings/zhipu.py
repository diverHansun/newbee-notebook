"""ZhipuAI Embedding builder.

Provides a factory function for LlamaIndex ZhipuAI embeddings (embedding-3).
Configuration priority: environment variable > YAML config > defaults.
"""

from typing import List, Dict, Any
import os

from llama_index.embeddings.zhipuai import ZhipuAIEmbedding

from newbee_notebook.core.common.config import (
    get_zhipu_api_key,
    get_embeddings_config,
)
from newbee_notebook.core.rag.embeddings.base import BaseEmbeddingModel
from newbee_notebook.core.rag.embeddings.registry import register_embedding


class ZhipuEmbeddingWrapper(BaseEmbeddingModel):
    """Wrapper for ZhipuAI Embedding to match BaseEmbeddingModel interface."""

    def __init__(self, zhipu_embedding: ZhipuAIEmbedding, model_name: str):
        super().__init__()
        self._zhipu_embedding = zhipu_embedding
        self._model_name = model_name

    @property
    def dimensions(self) -> int:
        return self._zhipu_embedding.dimensions

    @property
    def model_name(self) -> str:
        return self._model_name

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._zhipu_embedding._get_query_embedding(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._zhipu_embedding._get_text_embedding(text)

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self._zhipu_embedding._get_text_embeddings(texts)

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return await self._zhipu_embedding._aget_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return await self._zhipu_embedding._aget_text_embedding(text)

    async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return await self._zhipu_embedding._aget_text_embeddings(texts)


def _get_zhipu_config() -> Dict[str, Any]:
    embeddings_config = get_embeddings_config()
    return embeddings_config.get("embeddings", {}).get("zhipu", {})


@register_embedding("zhipu")
def build_zhipu_embedding(
    model: str | None = None,
    dimensions: int | None = None,
) -> BaseEmbeddingModel:
    """Build and return a ZhipuAI Embedding instance."""
    api_key = get_zhipu_api_key()
    if not api_key:
        raise ValueError(
            "ZHIPU_API_KEY not set. Please set it in environment variables or .env file"
        )

    config = _get_zhipu_config()

    final_model = model or os.getenv("EMBEDDING_MODEL") or config.get("model", "embedding-3")
    final_dimensions = int(
        dimensions
        or os.getenv("EMBEDDING_DIMENSION")
        or config.get("dim", 1024)
    )

    print(f"[ZhipuAI] Model: {final_model}, Dimensions: {final_dimensions}")

    zhipu_embedding = ZhipuAIEmbedding(
        model=final_model,
        api_key=api_key,
        dimensions=final_dimensions,
    )

    return ZhipuEmbeddingWrapper(
        zhipu_embedding=zhipu_embedding,
        model_name=f"zhipu-{final_model}",
    )


# Backward compatibility export expected by some tests
build_embedding = build_zhipu_embedding
