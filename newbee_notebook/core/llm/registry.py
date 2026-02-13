"""LLM provider registry for dynamic provider management."""

from typing import Callable, Dict, List
from llama_index.core.llms import LLM


_LLM_REGISTRY: Dict[str, Callable[[], LLM]] = {}


def register_llm(name: str):
    """Register an LLM provider builder."""

    def decorator(builder_func: Callable[[], LLM]):
        if name in _LLM_REGISTRY:
            raise ValueError(
                f"LLM provider '{name}' is already registered. "
                "Each provider must have a unique name."
            )
        _LLM_REGISTRY[name] = builder_func
        return builder_func

    return decorator


def get_registered_providers() -> List[str]:
    """Get all registered LLM provider names."""
    return sorted(_LLM_REGISTRY.keys())


def get_builder(provider: str) -> Callable[[], LLM]:
    """Get builder for a registered provider."""
    if provider not in _LLM_REGISTRY:
        available = get_registered_providers()
        raise ValueError(
            f"Unknown LLM provider: '{provider}'. "
            f"Available providers: {available}. "
            "Please check configs/llm.yaml or ensure the provider module is imported."
        )
    return _LLM_REGISTRY[provider]
