"""SQLAlchemy implementation of chat image repository."""

from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from newbee_notebook.domain.entities.chat_image import ChatImage
from newbee_notebook.domain.repositories.chat_image_repository import ChatImageRepository
from newbee_notebook.infrastructure.persistence.models import ChatImageModel


class ChatImageRepositoryImpl(ChatImageRepository):
    """SQLAlchemy-backed uploaded chat image repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: ChatImageModel) -> ChatImage:
        return ChatImage(
            image_id=str(model.id),
            session_id=str(model.session_id),
            storage_key=model.storage_key,
            mime_type=model.mime_type,
            size_bytes=model.size_bytes,
            width=model.width,
            height=model.height,
            sha256=model.sha256,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
        )

    async def create(self, image: ChatImage) -> ChatImage:
        model = ChatImageModel(
            id=uuid.UUID(image.image_id),
            session_id=uuid.UUID(image.session_id),
            storage_key=image.storage_key,
            mime_type=image.mime_type,
            size_bytes=image.size_bytes,
            width=image.width,
            height=image.height,
            sha256=image.sha256,
            created_at=image.created_at,
            updated_at=image.updated_at,
            deleted_at=image.deleted_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def get(self, image_id: str) -> ChatImage | None:
        try:
            image_uuid = uuid.UUID(image_id)
        except (ValueError, TypeError):
            return None
        result = await self._session.execute(
            select(ChatImageModel).where(ChatImageModel.id == image_uuid)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_ids(self, image_ids: list[str]) -> list[ChatImage]:
        image_uuids: list[uuid.UUID] = []
        for image_id in image_ids:
            try:
                image_uuids.append(uuid.UUID(image_id))
            except (ValueError, TypeError):
                continue
        if not image_uuids:
            return []
        result = await self._session.execute(
            select(ChatImageModel)
            .where(ChatImageModel.id.in_(image_uuids))
            .order_by(ChatImageModel.created_at.asc(), ChatImageModel.id.asc())
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def list_by_session(self, session_id: str) -> list[ChatImage]:
        try:
            session_uuid = uuid.UUID(session_id)
        except (ValueError, TypeError):
            return []
        result = await self._session.execute(
            select(ChatImageModel)
            .where(ChatImageModel.session_id == session_uuid)
            .order_by(ChatImageModel.created_at.asc(), ChatImageModel.id.asc())
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def soft_delete_by_session(self, session_id: str) -> int:
        try:
            session_uuid = uuid.UUID(session_id)
        except (ValueError, TypeError):
            return 0
        result = await self._session.execute(
            select(ChatImageModel).where(ChatImageModel.session_id == session_uuid)
        )
        models = result.scalars().all()
        now = datetime.now()
        count = 0
        for model in models:
            if model.deleted_at is None:
                model.deleted_at = now
                count += 1
        await self._session.flush()
        return count
