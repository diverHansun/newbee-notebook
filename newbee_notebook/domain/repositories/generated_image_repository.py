"""Repository interface for generated images."""

from __future__ import annotations

from abc import ABC, abstractmethod

from newbee_notebook.domain.entities.generated_image import GeneratedImage


class GeneratedImageRepository(ABC):
    """Repository interface for generated image persistence operations."""

    @abstractmethod
    async def get(self, image_id: str) -> GeneratedImage | None:
        """Get one generated image record by image ID."""

    @abstractmethod
    async def create(self, image: GeneratedImage) -> GeneratedImage:
        """Create one generated image record."""

    @abstractmethod
    async def list_by_session(self, session_id: str) -> list[GeneratedImage]:
        """List generated images in one session ordered by created time."""

    @abstractmethod
    async def list_by_message_ids(
        self,
        session_id: str,
        message_ids: list[int],
    ) -> list[GeneratedImage]:
        """List generated images associated with given message IDs."""

    @abstractmethod
    async def update_message_id(self, image_id: str, message_id: int) -> bool:
        """Backfill message_id for a generated image."""
