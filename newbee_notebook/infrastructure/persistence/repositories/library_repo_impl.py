"""
Newbee Notebook - Library Repository Implementation
"""

from typing import Optional
from datetime import datetime
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from newbee_notebook.domain.entities.library import Library
from newbee_notebook.domain.repositories.library_repository import LibraryRepository
from newbee_notebook.infrastructure.persistence.models import LibraryModel


class LibraryRepositoryImpl(LibraryRepository):
    """
    SQLAlchemy implementation of LibraryRepository.
    """
    
    def __init__(self, session: AsyncSession):
        self._session = session
    
    def _to_entity(self, model: LibraryModel) -> Library:
        """Convert ORM model to domain entity."""
        return Library(
            library_id=str(model.id),
            document_count=0,  # Computed from documents table
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    
    async def get(self) -> Optional[Library]:
        """Get the Library."""
        result = await self._session.execute(
            select(LibraryModel).limit(1)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
    
    async def create(self, library: Library) -> Library:
        """Create the Library."""
        model = LibraryModel(
            id=uuid.UUID(library.library_id),
            created_at=library.created_at,
            updated_at=library.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)
    
    async def update(self, library: Library) -> Library:
        """Update the Library."""
        await self._session.execute(
            update(LibraryModel)
            .where(LibraryModel.id == uuid.UUID(library.library_id))
            .values(updated_at=datetime.now())
        )
        await self._session.flush()
        return library
    
    async def get_or_create(self) -> Library:
        """Get the Library, creating it if it doesn't exist."""
        library = await self.get()
        if library is None:
            library = Library()
            library = await self.create(library)
        return library
    
    async def increment_document_count(self, delta: int = 1) -> None:
        """
        Increment the document count.
        
        Note: In this implementation, document_count is computed from
        the documents table rather than stored in the library table.
        This method is a no-op but kept for interface compatibility.
        """
        # Document count is computed dynamically from documents table
        pass


