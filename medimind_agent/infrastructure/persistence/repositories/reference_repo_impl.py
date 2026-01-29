"""
MediMind Agent - Reference Repository Implementation

Implements citation reference persistence using SQLAlchemy.
"""

from typing import Optional, List
import uuid

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from medimind_agent.domain.entities.reference import Reference
from medimind_agent.domain.repositories.reference_repository import ReferenceRepository
from medimind_agent.infrastructure.persistence.models import ReferenceModel


class ReferenceRepositoryImpl(ReferenceRepository):
    """
    SQLAlchemy implementation of ReferenceRepository.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, model: ReferenceModel) -> Reference:
        return Reference(
            reference_id=str(model.id),
            session_id=str(model.session_id),
            message_id=model.message_id or 0,
            document_id=str(model.document_id) if model.document_id else None,
            chunk_id=model.chunk_id or "",
            quoted_text=model.quoted_text,
            context=model.context,
            document_title=model.document_title,
            is_source_deleted=model.is_source_deleted,
            created_at=model.created_at,
            updated_at=model.created_at,
        )

    async def get(self, reference_id: str) -> Optional[Reference]:
        result = await self._session.execute(
            select(ReferenceModel).where(ReferenceModel.id == uuid.UUID(reference_id))
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_message(self, session_id: str, message_id: int) -> List[Reference]:
        result = await self._session.execute(
            select(ReferenceModel)
            .where(
                ReferenceModel.session_id == uuid.UUID(session_id),
                ReferenceModel.message_id == message_id,
            )
            .order_by(ReferenceModel.created_at.desc())
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def list_by_session(self, session_id: str) -> List[Reference]:
        result = await self._session.execute(
            select(ReferenceModel)
            .where(ReferenceModel.session_id == uuid.UUID(session_id))
            .order_by(ReferenceModel.created_at.desc())
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def create(self, reference: Reference) -> Reference:
        model = ReferenceModel(
            id=uuid.UUID(reference.reference_id),
            session_id=uuid.UUID(reference.session_id),
            message_id=reference.message_id,
            chunk_id=reference.chunk_id,
            document_id=uuid.UUID(reference.document_id) if reference.document_id else None,
            quoted_text=reference.quoted_text,
            context=reference.context,
            document_title=reference.document_title,
            is_source_deleted=reference.is_source_deleted,
            created_at=reference.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def create_batch(self, references: List[Reference]) -> List[Reference]:
        if not references:
            return []
        created = []
        for ref in references:
            created.append(await self.create(ref))
        return created

    async def delete(self, reference_id: str) -> bool:
        result = await self._session.execute(
            delete(ReferenceModel).where(ReferenceModel.id == uuid.UUID(reference_id))
        )
        await self._session.flush()
        return result.rowcount > 0

    async def delete_by_session(self, session_id: str) -> int:
        result = await self._session.execute(
            delete(ReferenceModel).where(ReferenceModel.session_id == uuid.UUID(session_id))
        )
        await self._session.flush()
        return result.rowcount

    async def mark_source_deleted(
        self,
        document_id: str,
        document_title: Optional[str] = None,
    ) -> int:
        """Mark references of a document as deleted while keeping quoted text."""
        from sqlalchemy import update

        result = await self._session.execute(
            update(ReferenceModel)
            .where(ReferenceModel.document_id == uuid.UUID(document_id))
            .values(
                document_id=None,
                document_title=document_title,
                is_source_deleted=True,
            )
        )
        await self._session.flush()
        return result.rowcount
