"""Repository interface for marks."""

from abc import ABC, abstractmethod
from typing import Optional

from newbee_notebook.domain.entities.mark import Mark


class MarkRepository(ABC):
    """Repository interface for mark operations."""

    @abstractmethod
    async def get(self, mark_id: str) -> Optional[Mark]:
        """Get a mark by ID."""
        pass

    @abstractmethod
    async def list_by_document(self, document_id: str) -> list[Mark]:
        """List marks for one document."""
        pass

    @abstractmethod
    async def create(self, mark: Mark) -> Mark:
        """Create a mark."""
        pass

    @abstractmethod
    async def delete(self, mark_id: str) -> bool:
        """Delete a mark."""
        pass
