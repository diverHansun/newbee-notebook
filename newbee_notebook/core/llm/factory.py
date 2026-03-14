"""Factory for cached runtime LLM clients."""

from __future__ import annotations

from typing import Callable

from newbee_notebook.core.llm.client import LLMClient
from newbee_notebook.core.llm.config import LLMRuntimeConfig


class LLMClientFactory:
    def __init__(self, client_builder: Callable[[LLMRuntimeConfig], object] | None = None):
        self._client_builder = client_builder or (lambda config: LLMClient(runtime_config=config))
        self._cached_key: tuple | None = None
        self._cached_client: object | None = None

    def get_client(self, config: LLMRuntimeConfig):
        key = config.cache_key
        if self._cached_client is not None and self._cached_key == key:
            return self._cached_client
        self._cached_key = key
        self._cached_client = self._client_builder(config)
        return self._cached_client

    def reset(self) -> None:
        self._cached_key = None
        self._cached_client = None
