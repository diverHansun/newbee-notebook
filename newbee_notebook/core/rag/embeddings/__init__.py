"""Embedding models for medical document vectorization.

This module provides flexible embedding model utilities with dynamic provider registration.

Supported providers (automatically registered):
- ZhipuAI embedding-3 (cloud API)
- BioBERT v1.1 (local model)

Registry pattern implementation following Open/Closed Principle (OCP).
Adding new providers requires ZERO modifications to this file.
"""

from newbee_notebook.core.common.config import get_embedding_provider
from newbee_notebook.core.rag.embeddings.base import BaseEmbeddingModel
from newbee_notebook.core.rag.embeddings.registry import get_builder, get_registered_providers

# Import provider modules to trigger @register_embedding decorators
# These imports execute the decorator code which adds providers to the registry
from newbee_notebook.core.rag.embeddings import biobert  # noqa: F401
from newbee_notebook.core.rag.embeddings import zhipu    # noqa: F401

# Re-export builder functions for backward compatibility
from newbee_notebook.core.rag.embeddings.biobert import build_biobert_embedding
from newbee_notebook.core.rag.embeddings.zhipu import build_zhipu_embedding


def build_embedding() -> BaseEmbeddingModel:
    """Build embedding model based on configuration.

    Factory function that creates the appropriate embedding model instance
    based on the selected provider in configs/embeddings.yaml (line 7: provider field).

    This function implements the Registry Pattern following SOLID principles:
    - OCP (Open/Closed): Adding new providers requires ZERO changes to this function
    - SRP (Single Responsibility): Only responsible for delegating to registered builders
    - DIP (Dependency Inversion): Returns base type, not concrete implementation

    The actual provider registration happens via @register_embedding decorators
    in each provider module (biobert.py, zhipu.py, etc.).

    Returns:
        BaseEmbeddingModel: Configured embedding model instance

    Raises:
        ValueError: If provider is not registered or config is invalid

    Examples:
        # Using BioBERT (set provider: biobert in embeddings.yaml line 7)
        >>> embed_model = build_embedding()
        >>> embed_model.model_name
        'biobert-768d'

        # Using ZhipuAI (set provider: zhipu in embeddings.yaml line 7)
        >>> embed_model = build_embedding()
        >>> embed_model.model_name
        'zhipu-embedding-3'
    """
    provider = get_embedding_provider()

    print(f"[Embedding] Using provider: {provider}")

    # Get builder from registry (automatically populated via decorators)
    builder = get_builder(provider)

    # Build and return embedding instance
    return builder()


__all__ = [
    # Main factory function
    "build_embedding",
    # Provider-specific builders (for direct use if needed)
    "build_biobert_embedding",
    "build_zhipu_embedding",
    # Base class
    "BaseEmbeddingModel",
    # Registry utilities (for introspection)
    "get_registered_providers",
]


