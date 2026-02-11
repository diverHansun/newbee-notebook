"""Base abstraction for embedding providers.

Defines a stable embedding interface used by the rest of the RAG stack.
"""

from abc import ABC, abstractmethod
from typing import List
from llama_index.core.embeddings import BaseEmbedding


class BaseEmbeddingModel(BaseEmbedding):
    """Abstract base class for custom embedding models."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return embedding vector dimension (e.g. 768, 1024)."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return provider/model identifier for logs and debugging."""
        pass

    @abstractmethod
    def _get_query_embedding(self, query: str) -> List[float]:
        """Generate an embedding vector for a query string."""
        pass

    @abstractmethod
    def _get_text_embedding(self, text: str) -> List[float]:
        """Generate an embedding vector for one text string."""
        pass

    @abstractmethod
    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for multiple text strings."""
        pass

    async def _aget_query_embedding(self, query: str) -> List[float]:
        """Async query embedding. Defaults to the sync implementation."""
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        """Async text embedding. Defaults to the sync implementation."""
        return self._get_text_embedding(text)

    async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Async batch text embeddings. Defaults to the sync implementation."""
        return self._get_text_embeddings(texts)
