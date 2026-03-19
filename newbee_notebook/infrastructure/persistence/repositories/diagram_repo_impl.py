"""SQLAlchemy implementation of the diagram repository."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from newbee_notebook.domain.entities.diagram import Diagram
from newbee_notebook.domain.repositories.diagram_repository import DiagramRepository
from newbee_notebook.infrastructure.persistence.models import DiagramModel


class DiagramRepositoryImpl(DiagramRepository):
    """SQLAlchemy-backed diagram repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: DiagramModel) -> Diagram:
        return Diagram(
            diagram_id=str(model.id),
            notebook_id=str(model.notebook_id),
            title=model.title,
            diagram_type=model.diagram_type,
            format=model.format,
            content_path=model.content_path,
            document_ids=[str(value) for value in (model.document_ids or [])],
            node_positions=model.node_positions,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get(self, diagram_id: str) -> Optional[Diagram]:
        result = await self._session.execute(
            select(DiagramModel).where(DiagramModel.id == uuid.UUID(diagram_id))
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_notebook(
        self,
        notebook_id: str,
        document_id: Optional[str] = None,
    ) -> list[Diagram]:
        query = (
            select(DiagramModel)
            .where(DiagramModel.notebook_id == uuid.UUID(notebook_id))
            .order_by(DiagramModel.updated_at.desc(), DiagramModel.created_at.desc())
        )
        if document_id is not None:
            query = query.where(DiagramModel.document_ids.any(uuid.UUID(document_id)))

        result = await self._session.execute(query)
        return [self._to_entity(model) for model in result.scalars().all()]

    async def create(self, diagram: Diagram) -> Diagram:
        model = DiagramModel(
            id=uuid.UUID(diagram.diagram_id),
            notebook_id=uuid.UUID(diagram.notebook_id),
            title=diagram.title,
            diagram_type=diagram.diagram_type,
            format=diagram.format,
            content_path=diagram.content_path,
            document_ids=[uuid.UUID(value) for value in diagram.document_ids],
            node_positions=diagram.node_positions,
            created_at=diagram.created_at,
            updated_at=diagram.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def update(self, diagram: Diagram) -> Diagram:
        result = await self._session.execute(
            select(DiagramModel).where(DiagramModel.id == uuid.UUID(diagram.diagram_id))
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"Diagram not found during update: {diagram.diagram_id}")

        model.title = diagram.title
        model.diagram_type = diagram.diagram_type
        model.format = diagram.format
        model.content_path = diagram.content_path
        model.document_ids = [uuid.UUID(value) for value in diagram.document_ids]
        model.node_positions = diagram.node_positions
        model.updated_at = diagram.updated_at
        await self._session.flush()
        return self._to_entity(model)

    async def delete(self, diagram_id: str) -> bool:
        result = await self._session.execute(
            delete(DiagramModel).where(DiagramModel.id == uuid.UUID(diagram_id))
        )
        await self._session.flush()
        return result.rowcount > 0
