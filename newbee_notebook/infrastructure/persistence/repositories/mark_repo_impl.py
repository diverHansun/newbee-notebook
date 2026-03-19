"""SQLAlchemy implementation of the mark repository."""

import uuid
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from newbee_notebook.domain.entities.mark import Mark
from newbee_notebook.domain.repositories.mark_repository import MarkRepository
from newbee_notebook.infrastructure.persistence.models import MarkModel


class MarkRepositoryImpl(MarkRepository):
    """SQLAlchemy-backed mark repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, model: MarkModel) -> Mark:
        return Mark(
            mark_id=str(model.id),
            document_id=str(model.document_id),
            anchor_text=model.anchor_text,
            char_offset=model.char_offset,
            context_text=model.context_text,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get(self, mark_id: str) -> Optional[Mark]:
        result = await self._session.execute(
            select(MarkModel).where(MarkModel.id == uuid.UUID(mark_id))
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_document(self, document_id: str) -> list[Mark]:
        result = await self._session.execute(
            select(MarkModel)
            .where(MarkModel.document_id == uuid.UUID(document_id))
            .order_by(MarkModel.char_offset.asc(), MarkModel.created_at.asc())
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def create(self, mark: Mark) -> Mark:
        model = MarkModel(
            id=uuid.UUID(mark.mark_id),
            document_id=uuid.UUID(mark.document_id),
            anchor_text=mark.anchor_text,
            char_offset=mark.char_offset,
            context_text=mark.context_text,
            created_at=mark.created_at,
            updated_at=mark.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def delete(self, mark_id: str) -> bool:
        result = await self._session.execute(
            delete(MarkModel).where(MarkModel.id == uuid.UUID(mark_id))
        )
        await self._session.flush()
        return result.rowcount > 0
