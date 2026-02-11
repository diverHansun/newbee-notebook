"""
Newbee Notebook - NotebookDocumentRef Repository Implementation
"""

from typing import Optional, List
import uuid

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from newbee_notebook.domain.entities.reference import NotebookDocumentRef
from newbee_notebook.domain.repositories.reference_repository import NotebookDocumentRefRepository
from newbee_notebook.infrastructure.persistence.models import NotebookDocumentRefModel


class NotebookDocumentRefRepositoryImpl(NotebookDocumentRefRepository):
    """
    SQLAlchemy implementation of NotebookDocumentRefRepository.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, model: NotebookDocumentRefModel) -> NotebookDocumentRef:
        return NotebookDocumentRef(
            reference_id=str(model.id),
            notebook_id=str(model.notebook_id),
            document_id=str(model.document_id),
            created_at=model.created_at,
            updated_at=model.created_at,
        )

    async def get(self, reference_id: str) -> Optional[NotebookDocumentRef]:
        result = await self._session.execute(
            select(NotebookDocumentRefModel).where(
                NotebookDocumentRefModel.id == uuid.UUID(reference_id)
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_notebook_and_document(
        self, notebook_id: str, document_id: str
    ) -> Optional[NotebookDocumentRef]:
        result = await self._session.execute(
            select(NotebookDocumentRefModel).where(
                NotebookDocumentRefModel.notebook_id == uuid.UUID(notebook_id),
                NotebookDocumentRefModel.document_id == uuid.UUID(document_id),
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_notebook(self, notebook_id: str) -> List[NotebookDocumentRef]:
        result = await self._session.execute(
            select(NotebookDocumentRefModel)
            .where(NotebookDocumentRefModel.notebook_id == uuid.UUID(notebook_id))
            .order_by(NotebookDocumentRefModel.created_at.desc())
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def list_by_document(self, document_id: str) -> List[NotebookDocumentRef]:
        result = await self._session.execute(
            select(NotebookDocumentRefModel)
            .where(NotebookDocumentRefModel.document_id == uuid.UUID(document_id))
            .order_by(NotebookDocumentRefModel.created_at.desc())
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def count_by_document(self, document_id: str) -> int:
        # Reuse list_by_document to avoid another COUNT query for small cardinality
        refs = await self.list_by_document(document_id)
        return len(refs)

    async def create(self, ref: NotebookDocumentRef) -> NotebookDocumentRef:
        model = NotebookDocumentRefModel(
            id=uuid.UUID(ref.reference_id),
            notebook_id=uuid.UUID(ref.notebook_id),
            document_id=uuid.UUID(ref.document_id),
            created_at=ref.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def delete(self, reference_id: str) -> bool:
        result = await self._session.execute(
            delete(NotebookDocumentRefModel).where(
                NotebookDocumentRefModel.id == uuid.UUID(reference_id)
            )
        )
        await self._session.flush()
        return result.rowcount > 0

    async def delete_by_notebook(self, notebook_id: str) -> int:
        result = await self._session.execute(
            delete(NotebookDocumentRefModel).where(
                NotebookDocumentRefModel.notebook_id == uuid.UUID(notebook_id)
            )
        )
        await self._session.flush()
        return result.rowcount

    async def delete_by_document(self, document_id: str) -> int:
        result = await self._session.execute(
            delete(NotebookDocumentRefModel).where(
                NotebookDocumentRefModel.document_id == uuid.UUID(document_id)
            )
        )
        await self._session.flush()
        return result.rowcount


