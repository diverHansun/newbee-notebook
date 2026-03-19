"""Repository interface for notes."""

from abc import ABC, abstractmethod
from typing import Optional

from newbee_notebook.domain.entities.note import Note


class NoteRepository(ABC):
    """Repository interface for note operations."""

    @abstractmethod
    async def get(self, note_id: str) -> Optional[Note]:
        """Get a note by ID."""
        pass

    @abstractmethod
    async def list_by_notebook(self, notebook_id: str) -> list[Note]:
        """List notes for one notebook."""
        pass

    @abstractmethod
    async def create(self, note: Note) -> Note:
        """Create a note."""
        pass

    @abstractmethod
    async def update(self, note: Note) -> Note:
        """Update a note."""
        pass

    @abstractmethod
    async def delete(self, note_id: str) -> bool:
        """Delete a note."""
        pass

    @abstractmethod
    async def sync_mark_refs(self, note_id: str, mark_ids: list[str]) -> None:
        """Replace parsed mark references for a note."""
        pass
