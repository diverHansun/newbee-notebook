"""Embedding provider registry for dynamic provider management.

This module implements the Registry Pattern to enable adding new embedding
providers without modifying existing code, following the Open/Closed Principle (OCP).

Key principles applied:
- OCP: New providers can be added by creating new files without modifying this registry
- SRP: This module has a single responsibility - managing provider registration
- DRY: Centralized provider lookup logic eliminates duplicate provider checking
"""

from typing import Callable, Dict, List
from newbee_notebook.core.rag.embeddings.base import BaseEmbeddingModel


# Global registry for embedding providers
_EMBEDDING_REGISTRY: Dict[str, Callable[[], BaseEmbeddingModel]] = {}


def register_embedding(name: str):
    """Decorator for registering embedding provider builders.

    This decorator enables automatic registration when provider modules are imported.
    Follows the Dependency Inversion Principle (DIP) by working with callable builders
    that return BaseEmbeddingModel instances.

    Args:
        name: Provider name (e.g., 'biobert', 'zhipu', 'openai')

    Returns:
        Decorator function that registers the builder

    Example:
        >>> @register_embedding("biobert")
        ... def build_biobert_embedding() -> BaseEmbeddingModel:
        ...     return BioBERTEmbedding(...)

    Raises:
        ValueError: If provider name is already registered
    """
    def decorator(builder_func: Callable[[], BaseEmbeddingModel]):
        if name in _EMBEDDING_REGISTRY:
            raise ValueError(
                f"Embedding provider '{name}' is already registered. "
                f"Each provider must have a unique name."
            )
        _EMBEDDING_REGISTRY[name] = builder_func
        return builder_func
    return decorator


def get_registered_providers() -> List[str]:
    """Get list of all registered embedding providers.

    Returns:
        List of provider names (e.g., ['biobert', 'zhipu'])

    Example:
        >>> providers = get_registered_providers()
        >>> print(f"Available providers: {providers}")
    """
    return sorted(_EMBEDDING_REGISTRY.keys())


def get_builder(provider: str) -> Callable[[], BaseEmbeddingModel]:
    """Get builder function for specified provider.

    Args:
        provider: Provider name (e.g., 'biobert', 'zhipu')

    Returns:
        Builder function that creates BaseEmbeddingModel instance

    Raises:
        ValueError: If provider is not registered

    Example:
        >>> builder = get_builder("biobert")
        >>> embed_model = builder()
    """
    if provider not in _EMBEDDING_REGISTRY:
        available = get_registered_providers()
        raise ValueError(
            f"Unknown embedding provider: '{provider}'. "
            f"Available providers: {available}. "
            f"Please check configs/embeddings.yaml or ensure the provider module is imported."
        )
    return _EMBEDDING_REGISTRY[provider]


def is_registered(provider: str) -> bool:
    """Check if a provider is registered.

    Args:
        provider: Provider name to check

    Returns:
        True if provider is registered, False otherwise

    Example:
        >>> if is_registered("biobert"):
        ...     print("BioBERT is available")
    """
    return provider in _EMBEDDING_REGISTRY


