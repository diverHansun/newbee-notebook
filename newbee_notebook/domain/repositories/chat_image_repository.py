"""Repository interface for uploaded chat images."""

from __future__ import annotations

from abc import ABC, abstractmethod

from newbee_notebook.domain.entities.chat_image import ChatImage


class ChatImageRepository(ABC):
    """Persistence operations for user-uploaded chat image metadata."""

    @abstractmethod
    async def create(self, image: ChatImage) -> ChatImage:
        """Create one chat image metadata record."""

    @abstractmethod
    async def get(self, image_id: str) -> ChatImage | None:
        """Get one chat image by ID."""

    @abstractmethod
    async def list_by_ids(self, image_ids: list[str]) -> list[ChatImage]:
        """List images for the supplied IDs."""

    @abstractmethod
    async def list_by_session(self, session_id: str) -> list[ChatImage]:
        """List uploaded chat images for one session."""

    @abstractmethod
    async def soft_delete_by_session(self, session_id: str) -> int:
        """Mark all images in a session as deleted."""
