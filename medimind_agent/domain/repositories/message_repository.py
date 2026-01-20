"""Repository interface for messages."""

from abc import ABC, abstractmethod
from typing import List

from medimind_agent.domain.entities.message import Message


class MessageRepository(ABC):
    @abstractmethod
    async def create(self, message: Message) -> Message:
        pass

    @abstractmethod
    async def create_batch(self, messages: List[Message]) -> List[Message]:
        pass

    @abstractmethod
    async def list_by_session(self, session_id: str, limit: int = 100) -> List[Message]:
        pass
