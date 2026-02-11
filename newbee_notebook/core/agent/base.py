"""Base interfaces for agent runners.

Defines a lightweight abstraction so modes depend on a stable interface
instead of concrete LlamaIndex workflow classes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Protocol

from llama_index.core.llms import ChatMessage


class SupportsWorkflowAgent(Protocol):
    """Protocol for workflow-based agents used by runners."""

    async def run(  # pragma: no cover - delegated to LlamaIndex
        self,
        user_msg: str,
        chat_history: Optional[List[ChatMessage]] = None,
        **kwargs,
    ):
        ...


class AgentRunner(ABC):
    """Minimal async runner interface for workflow-based agents."""

    @abstractmethod
    async def run(
        self,
        message: str,
        chat_history: Optional[List[ChatMessage]] = None,
    ) -> str:
        """Execute the agent and return its response."""
        raise NotImplementedError

    @property
    @abstractmethod
    def agent(self) -> SupportsWorkflowAgent:
        """Expose the underlying agent for tooling access."""
        raise NotImplementedError


