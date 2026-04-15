"""Application service for generated image metadata and content access."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from newbee_notebook.domain.entities.base import generate_uuid
from newbee_notebook.domain.entities.generated_image import GeneratedImage
from newbee_notebook.domain.repositories.generated_image_repository import (
    GeneratedImageRepository,
)
from newbee_notebook.infrastructure.storage.base import StorageBackend


class GeneratedImageNotFoundError(Exception):
    """Raised when generated image metadata or binary content cannot be found."""


@dataclass(frozen=True)
class GeneratedImageContent:
    image: GeneratedImage
    data: bytes


class GeneratedImageService:
    """Read/write operations for generated images."""

    def __init__(
        self,
        generated_image_repo: GeneratedImageRepository,
        storage: StorageBackend,
    ):
        self._generated_image_repo = generated_image_repo
        self._storage = storage

    async def create(
        self,
        *,
        session_id: str,
        notebook_id: str,
        prompt: str,
        provider: str,
        model: str,
        storage_key: str,
        tool_call_id: str = "",
        message_id: int | None = None,
        size: str | None = None,
        width: int | None = None,
        height: int | None = None,
        file_size: int = 0,
        image_id: str | None = None,
    ) -> GeneratedImage:
        image = GeneratedImage(
            image_id=image_id or generate_uuid(),
            session_id=session_id,
            notebook_id=notebook_id,
            message_id=message_id,
            tool_call_id=tool_call_id,
            prompt=prompt,
            provider=provider,
            model=model,
            size=size,
            width=width,
            height=height,
            storage_key=storage_key,
            file_size=file_size,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        return await self._generated_image_repo.create(image)

    async def get(self, image_id: str) -> GeneratedImage:
        image = await self._generated_image_repo.get(image_id)
        if image is None:
            raise GeneratedImageNotFoundError(f"Generated image not found: {image_id}")
        return image

    async def list_by_session(self, session_id: str) -> list[GeneratedImage]:
        return await self._generated_image_repo.list_by_session(session_id)

    async def list_by_message_ids(
        self,
        session_id: str,
        message_ids: list[int],
    ) -> list[GeneratedImage]:
        return await self._generated_image_repo.list_by_message_ids(session_id, message_ids)

    async def backfill_message_ids(self, image_ids: list[str], message_id: int) -> None:
        for image_id in image_ids:
            await self._generated_image_repo.update_message_id(image_id, message_id)

    async def get_binary(self, image_id: str) -> GeneratedImageContent:
        image = await self.get(image_id)
        try:
            data = await self._storage.get_file(image.storage_key)
        except FileNotFoundError as exc:
            raise GeneratedImageNotFoundError(
                f"Generated image binary not found for {image_id}: {image.storage_key}"
            ) from exc
        return GeneratedImageContent(image=image, data=data)
