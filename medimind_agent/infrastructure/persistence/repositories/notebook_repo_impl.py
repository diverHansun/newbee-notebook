"""
MediMind Agent - Notebook Repository Implementation
"""

from typing import Optional, List
from datetime import datetime
import uuid

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from medimind_agent.domain.entities.notebook import Notebook
from medimind_agent.domain.repositories.notebook_repository import NotebookRepository
from medimind_agent.infrastructure.persistence.models import NotebookModel


class NotebookRepositoryImpl(NotebookRepository):
    """
    SQLAlchemy implementation of NotebookRepository.
    """
    
    def __init__(self, session: AsyncSession):
        self._session = session
    
    def _to_entity(self, model: NotebookModel) -> Notebook:
        """Convert ORM model to domain entity."""
        return Notebook(
            notebook_id=str(model.id),
            title=model.title,
            description=model.description,
            session_count=model.session_count,
            document_count=model.document_count,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    
    async def get(self, notebook_id: str) -> Optional[Notebook]:
        """Get a Notebook by ID."""
        result = await self._session.execute(
            select(NotebookModel).where(NotebookModel.id == uuid.UUID(notebook_id))
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
    
    async def list(
        self, 
        limit: int = 20, 
        offset: int = 0,
        order_by: str = "updated_at",
        desc: bool = True
    ) -> List[Notebook]:
        """List all Notebooks with pagination."""
        order_column = getattr(NotebookModel, order_by, NotebookModel.updated_at)
        if desc:
            order_column = order_column.desc()
        
        result = await self._session.execute(
            select(NotebookModel)
            .order_by(order_column)
            .limit(limit)
            .offset(offset)
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]
    
    async def count(self) -> int:
        """Count total Notebooks."""
        result = await self._session.execute(
            select(func.count(NotebookModel.id))
        )
        return result.scalar() or 0
    
    async def create(self, notebook: Notebook) -> Notebook:
        """Create a Notebook."""
        model = NotebookModel(
            id=uuid.UUID(notebook.notebook_id),
            title=notebook.title,
            description=notebook.description,
            session_count=notebook.session_count,
            document_count=notebook.document_count,
            created_at=notebook.created_at,
            updated_at=notebook.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)
    
    async def update(self, notebook: Notebook) -> Notebook:
        """Update a Notebook."""
        await self._session.execute(
            update(NotebookModel)
            .where(NotebookModel.id == uuid.UUID(notebook.notebook_id))
            .values(
                title=notebook.title,
                description=notebook.description,
                session_count=notebook.session_count,
                document_count=notebook.document_count,
                updated_at=datetime.now(),
            )
        )
        await self._session.flush()
        return notebook
    
    async def delete(self, notebook_id: str) -> bool:
        """Delete a Notebook."""
        result = await self._session.execute(
            delete(NotebookModel).where(NotebookModel.id == uuid.UUID(notebook_id))
        )
        await self._session.flush()
        return result.rowcount > 0
    
    async def increment_session_count(self, notebook_id: str, delta: int = 1) -> None:
        """Increment the session count."""
        await self._session.execute(
            update(NotebookModel)
            .where(NotebookModel.id == uuid.UUID(notebook_id))
            .values(
                session_count=NotebookModel.session_count + delta,
                updated_at=datetime.now(),
            )
        )
        await self._session.flush()
    
    async def increment_document_count(self, notebook_id: str, delta: int = 1) -> None:
        """Increment the document count."""
        await self._session.execute(
            update(NotebookModel)
            .where(NotebookModel.id == uuid.UUID(notebook_id))
            .values(
                document_count=NotebookModel.document_count + delta,
                updated_at=datetime.now(),
            )
        )
        await self._session.flush()


