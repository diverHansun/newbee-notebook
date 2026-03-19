"""Repository interface for diagrams."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from newbee_notebook.domain.entities.diagram import Diagram


class DiagramRepository(ABC):
    """Repository interface for diagram persistence operations."""

    @abstractmethod
    async def get(self, diagram_id: str) -> Optional[Diagram]:
        """Get a diagram by ID."""

    @abstractmethod
    async def list_by_notebook(
        self,
        notebook_id: str,
        document_id: Optional[str] = None,
    ) -> list[Diagram]:
        """List diagrams under one notebook, optionally filtered by document."""

    @abstractmethod
    async def create(self, diagram: Diagram) -> Diagram:
        """Create a new diagram."""

    @abstractmethod
    async def update(self, diagram: Diagram) -> Diagram:
        """Update mutable fields for one diagram."""

    @abstractmethod
    async def delete(self, diagram_id: str) -> bool:
        """Delete a diagram by ID."""
