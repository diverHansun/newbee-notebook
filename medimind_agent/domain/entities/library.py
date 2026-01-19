"""
MediMind Agent - Library Entity

The Library is the global document storage for the single-user model.
Documents in the Library can be referenced by multiple Notebooks.
"""

from dataclasses import dataclass, field
from datetime import datetime
from medimind_agent.domain.entities.base import Entity, generate_uuid


@dataclass
class Library(Entity):
    """
    Library entity - global document storage.
    
    There is only one Library per deployment (single-user model).
    Documents in Library can be referenced by multiple Notebooks.
    
    Attributes:
        library_id: Unique identifier for the library
        document_count: Number of documents in the library
    """
    library_id: str = field(default_factory=generate_uuid)
    document_count: int = 0
    
    def increment_document_count(self, delta: int = 1) -> None:
        """Increment the document count."""
        self.document_count += delta
        self.touch()
    
    def decrement_document_count(self, delta: int = 1) -> None:
        """Decrement the document count."""
        self.document_count = max(0, self.document_count - delta)
        self.touch()


