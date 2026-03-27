"""Repository interface for messages."""

from abc import ABC, abstractmethod
from typing import List, Optional

from newbee_notebook.domain.entities.message import Message
from newbee_notebook.domain.value_objects.mode_type import ModeType


class MessageRepository(ABC):
    @abstractmethod
    async def create(self, message: Message) -> Message:
        pass

    @abstractmethod
    async def create_batch(self, messages: List[Message]) -> List[Message]:
        pass

    @abstractmethod
    async def list_by_session(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
        modes: Optional[List[ModeType]] = None,
    ) -> List[Message]:
        pass

    @abstractmethod
    async def count_by_session(
        self,
        session_id: str,
        modes: Optional[List[ModeType]] = None,
    ) -> int:
        pass

    @abstractmethod
    async def list_after_boundary(
        self,
        session_id: str,
        boundary_message_id: int | None,
        track_modes: Optional[List[ModeType]] = None,
    ) -> List[Message]:
        pass
