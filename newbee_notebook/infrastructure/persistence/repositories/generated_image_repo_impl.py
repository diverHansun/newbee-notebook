"""SQLAlchemy implementation of generated image repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from newbee_notebook.domain.entities.generated_image import GeneratedImage
from newbee_notebook.domain.repositories.generated_image_repository import (
    GeneratedImageRepository,
)
from newbee_notebook.infrastructure.persistence.models import GeneratedImageModel


class GeneratedImageRepositoryImpl(GeneratedImageRepository):
    """SQLAlchemy-backed generated image repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: GeneratedImageModel) -> GeneratedImage:
        return GeneratedImage(
            image_id=str(model.id),
            session_id=str(model.session_id),
            notebook_id=str(model.notebook_id),
            message_id=model.message_id,
            tool_call_id=model.tool_call_id,
            prompt=model.prompt,
            provider=model.provider,
            model=model.model,
            size=model.size,
            width=model.width,
            height=model.height,
            storage_key=model.storage_key,
            file_size=model.file_size,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get(self, image_id: str) -> GeneratedImage | None:
        try:
            image_uuid = uuid.UUID(image_id)
        except (ValueError, TypeError):
            return None
        result = await self._session.execute(
            select(GeneratedImageModel).where(GeneratedImageModel.id == image_uuid)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def create(self, image: GeneratedImage) -> GeneratedImage:
        model = GeneratedImageModel(
            id=uuid.UUID(image.image_id),
            session_id=uuid.UUID(image.session_id),
            notebook_id=uuid.UUID(image.notebook_id),
            message_id=image.message_id,
            tool_call_id=image.tool_call_id,
            prompt=image.prompt,
            provider=image.provider,
            model=image.model,
            size=image.size,
            width=image.width,
            height=image.height,
            storage_key=image.storage_key,
            file_size=image.file_size,
            created_at=image.created_at,
            updated_at=image.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def list_by_session(self, session_id: str) -> list[GeneratedImage]:
        try:
            session_uuid = uuid.UUID(session_id)
        except (ValueError, TypeError):
            return []
        result = await self._session.execute(
            select(GeneratedImageModel)
            .where(GeneratedImageModel.session_id == session_uuid)
            .order_by(GeneratedImageModel.created_at.asc(), GeneratedImageModel.id.asc())
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def list_by_message_ids(
        self,
        session_id: str,
        message_ids: list[int],
    ) -> list[GeneratedImage]:
        if not message_ids:
            return []
        try:
            session_uuid = uuid.UUID(session_id)
        except (ValueError, TypeError):
            return []
        result = await self._session.execute(
            select(GeneratedImageModel)
            .where(GeneratedImageModel.session_id == session_uuid)
            .where(GeneratedImageModel.message_id.in_(message_ids))
            .order_by(
                GeneratedImageModel.message_id.asc(),
                GeneratedImageModel.created_at.asc(),
                GeneratedImageModel.id.asc(),
            )
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def update_message_id(self, image_id: str, message_id: int) -> bool:
        try:
            image_uuid = uuid.UUID(image_id)
        except (ValueError, TypeError):
            return False
        result = await self._session.execute(
            select(GeneratedImageModel).where(GeneratedImageModel.id == image_uuid)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        model.message_id = message_id
        await self._session.flush()
        return True
