"""Embedding builders with registry-based provider selection.

Supported providers:
- qwen3-embedding (default)
- zhipu
"""

from newbee_notebook.core.common.config import get_embedding_provider
from newbee_notebook.core.rag.embeddings.base import BaseEmbeddingModel
from newbee_notebook.core.rag.embeddings.registry import get_builder, get_registered_providers

# Import provider modules to trigger @register_embedding decorators
# These imports execute decorator registration at import time.
from newbee_notebook.core.rag.embeddings import zhipu    # noqa: F401
from newbee_notebook.core.rag.embeddings import qwen3_embedding  # noqa: F401

# Re-export builder functions for backward compatibility
from newbee_notebook.core.rag.embeddings.zhipu import build_zhipu_embedding
from newbee_notebook.core.rag.embeddings.qwen3_embedding import build_qwen3_embedding


def build_embedding() -> BaseEmbeddingModel:
    """Build embedding model from `embeddings.provider`."""
    provider = get_embedding_provider()
    print(f"[Embedding] Using provider: {provider}")

    builder = get_builder(provider)
    return builder()


__all__ = [
    # Main factory function
    "build_embedding",
    # Provider-specific builders (for direct use if needed)
    "build_qwen3_embedding",
    "build_zhipu_embedding",
    # Base class
    "BaseEmbeddingModel",
    # Registry utilities (for introspection)
    "get_registered_providers",
]


