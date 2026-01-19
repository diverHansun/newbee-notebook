"""ZhipuAI Embedding builder.

Provides a factory function for LlamaIndex ZhipuAI embeddings (embedding-3).
Configuration priority: YAML config > environment variable > defaults.
"""

from typing import List, Dict, Any
from llama_index.embeddings.zhipuai import ZhipuAIEmbedding
from medimind_agent.core.common.config import (
    get_zhipu_api_key,
    get_embeddings_config,
)
from medimind_agent.core.rag.embeddings.base import BaseEmbeddingModel
from medimind_agent.core.rag.embeddings.registry import register_embedding


class ZhipuEmbeddingWrapper(BaseEmbeddingModel):
    """Wrapper for ZhipuAI Embedding to match BaseEmbeddingModel interface.

    Provides consistent interface across all embedding providers.
    Delegates actual embedding computation to LlamaIndex's ZhipuAIEmbedding.
    """

    def __init__(self, zhipu_embedding: ZhipuAIEmbedding, model_name: str):
        """Initialize wrapper.

        Args:
            zhipu_embedding: ZhipuAIEmbedding instance
            model_name: Model name for logging
        """
        super().__init__()
        self._zhipu_embedding = zhipu_embedding
        self._model_name = model_name

    @property
    def dimensions(self) -> int:
        """Return embedding dimension."""
        return self._zhipu_embedding.dimensions

    @property
    def model_name(self) -> str:
        """Return model name."""
        return self._model_name

    def _get_query_embedding(self, query: str) -> List[float]:
        """Get query embedding."""
        return self._zhipu_embedding._get_query_embedding(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        """Get text embedding."""
        return self._zhipu_embedding._get_text_embedding(text)

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get batch text embeddings."""
        return self._zhipu_embedding._get_text_embeddings(texts)

    async def _aget_query_embedding(self, query: str) -> List[float]:
        """Get query embedding asynchronously."""
        return await self._zhipu_embedding._aget_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        """Get text embedding asynchronously."""
        return await self._zhipu_embedding._aget_text_embedding(text)

    async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get batch text embeddings asynchronously."""
        return await self._zhipu_embedding._aget_text_embeddings(texts)


def _get_zhipu_config() -> Dict[str, Any]:
    """Get ZhipuAI-specific configuration from embeddings.yaml.

    Follows SRP: This function has a single responsibility - read ZhipuAI config.
    Follows DRY: Centralizes ZhipuAI config reading logic in one place.

    Returns:
        Dictionary containing ZhipuAI configuration:
        - model: Model name (default: 'embedding-3')
        - dim: Embedding dimension (default: 1024)

    Example:
        >>> config = _get_zhipu_config()
        >>> model = config.get('model', 'embedding-3')
    """
    embeddings_config = get_embeddings_config()
    return embeddings_config.get('embeddings', {}).get('zhipu', {})


@register_embedding("zhipu")
def build_zhipu_embedding() -> BaseEmbeddingModel:
    """Build and return a ZhipuAI Embedding instance.

    Factory function following Dependency Inversion Principle (DIP).
    Automatically registered as 'zhipu' provider via decorator.

    Configuration priority:
    1. configs/embeddings.yaml (zhipu section)
    2. Defaults (embedding-3, 1024 dimensions)

    Returns:
        BaseEmbeddingModel: Configured embedding instance

    Raises:
        ValueError: If ZHIPU_API_KEY is not set

    Example:
        >>> embed_model = build_zhipu_embedding()
        >>> dim = embed_model.dimensions  # Returns 1024
        >>> embeddings = embed_model.get_text_embeddings(["sample text"])
    """
    # Get API key (required)
    api_key = get_zhipu_api_key()
    if not api_key:
        raise ValueError(
            "ZHIPU_API_KEY not set. Please set it in environment variables or .env file"
        )

    # Get zhipu-specific configuration
    config = _get_zhipu_config()

    model = config.get('model', 'embedding-3')
    dimensions = config.get('dim', 1024)  # ZhipuAI embedding-3 default is 1024

    print(f"[ZhipuAI] Model: {model}, Dimensions: {dimensions}")

    # Create ZhipuAI embedding instance
    zhipu_embedding = ZhipuAIEmbedding(
        model=model,
        api_key=api_key,
        dimensions=dimensions
    )

    # Wrap it to match BaseEmbeddingModel interface
    return ZhipuEmbeddingWrapper(
        zhipu_embedding=zhipu_embedding,
        model_name=f"zhipu-{model}"
    )

# Backward compatibility export expected by some tests
build_embedding = build_zhipu_embedding

