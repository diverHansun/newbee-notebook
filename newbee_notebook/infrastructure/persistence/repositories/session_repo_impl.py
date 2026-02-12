"""
Newbee Notebook - Session Repository Implementation
"""

from typing import Optional, List
from datetime import datetime
import uuid

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from newbee_notebook.domain.entities.session import Session
from newbee_notebook.domain.repositories.session_repository import SessionRepository
from newbee_notebook.infrastructure.persistence.models import SessionModel


class SessionRepositoryImpl(SessionRepository):
    """
    SQLAlchemy implementation of SessionRepository.
    """
    
    def __init__(self, session: AsyncSession):
        self._session = session
    
    def _to_entity(self, model: SessionModel) -> Session:
        """Convert ORM model to domain entity."""
        return Session(
            session_id=str(model.id),
            notebook_id=str(model.notebook_id),
            title=model.title,
            message_count=model.message_count,
            context_summary=model.context_summary,
            include_ec_context=getattr(model, "include_ec_context", False),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    
    async def get(self, session_id: str) -> Optional[Session]:
        """Get a Session by ID."""
        result = await self._session.execute(
            select(SessionModel).where(SessionModel.id == uuid.UUID(session_id))
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
    
    async def list_by_notebook(
        self,
        notebook_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Session]:
        """List Sessions in a Notebook, ordered by updated_at DESC."""
        result = await self._session.execute(
            select(SessionModel)
            .where(SessionModel.notebook_id == uuid.UUID(notebook_id))
            .order_by(SessionModel.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]
    
    async def get_latest_by_notebook(self, notebook_id: str) -> Optional[Session]:
        """Get the most recently updated Session in a Notebook."""
        result = await self._session.execute(
            select(SessionModel)
            .where(SessionModel.notebook_id == uuid.UUID(notebook_id))
            .order_by(SessionModel.updated_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
    
    async def count_by_notebook(self, notebook_id: str) -> int:
        """Count Sessions in a Notebook."""
        result = await self._session.execute(
            select(func.count(SessionModel.id))
            .where(SessionModel.notebook_id == uuid.UUID(notebook_id))
        )
        return result.scalar() or 0
    
    async def create(self, session: Session) -> Session:
        """Create a Session."""
        model = SessionModel(
            id=uuid.UUID(session.session_id),
            notebook_id=uuid.UUID(session.notebook_id),
            title=session.title,
            message_count=session.message_count,
            context_summary=session.context_summary,
            include_ec_context=session.include_ec_context,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)
    
    async def update(self, session: Session) -> Session:
        """Update a Session."""
        await self._session.execute(
            update(SessionModel)
            .where(SessionModel.id == uuid.UUID(session.session_id))
            .values(
                title=session.title,
                message_count=session.message_count,
                context_summary=session.context_summary,
                include_ec_context=session.include_ec_context,
                updated_at=datetime.now(),
            )
        )
        await self._session.flush()
        return session
    
    async def delete(self, session_id: str) -> bool:
        """Delete a Session."""
        result = await self._session.execute(
            delete(SessionModel).where(SessionModel.id == uuid.UUID(session_id))
        )
        await self._session.flush()
        return result.rowcount > 0
    
    async def delete_by_notebook(self, notebook_id: str) -> int:
        """Delete all Sessions in a Notebook."""
        result = await self._session.execute(
            delete(SessionModel)
            .where(SessionModel.notebook_id == uuid.UUID(notebook_id))
        )
        await self._session.flush()
        return result.rowcount
    
    async def increment_message_count(self, session_id: str, delta: int = 1) -> None:
        """Increment the message count."""
        await self._session.execute(
            update(SessionModel)
            .where(SessionModel.id == uuid.UUID(session_id))
            .values(
                message_count=SessionModel.message_count + delta,
                updated_at=datetime.now(),
            )
        )
        await self._session.flush()
    
    async def update_context_summary(self, session_id: str, summary: str) -> None:
        """Update the context summary."""
        await self._session.execute(
            update(SessionModel)
            .where(SessionModel.id == uuid.UUID(session_id))
            .values(
                context_summary=summary,
                updated_at=datetime.now(),
            )
        )
        await self._session.flush()


