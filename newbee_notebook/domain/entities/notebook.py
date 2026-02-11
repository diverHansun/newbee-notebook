"""
Newbee Notebook - Notebook Entity

A Notebook is a workspace for documents and conversations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from newbee_notebook.domain.entities.base import Entity, generate_uuid


# Maximum number of sessions allowed per notebook
MAX_SESSIONS_PER_NOTEBOOK = 20


@dataclass
class Notebook(Entity):
    """
    Notebook entity - a workspace for documents and conversations.
    
    Each Notebook can have:
    - Up to 20 Sessions
    - Documents (either owned or referenced from Library)
    
    Attributes:
        notebook_id: Unique identifier
        title: Notebook title
        description: Optional description
        session_count: Current number of sessions
        document_count: Number of owned documents (not including references)
    """
    notebook_id: str = field(default_factory=generate_uuid)
    title: str = ""
    description: Optional[str] = None
    session_count: int = 0
    document_count: int = 0
    
    def can_create_session(self) -> bool:
        """Check if a new session can be created."""
        return self.session_count < MAX_SESSIONS_PER_NOTEBOOK
    
    def increment_session_count(self, delta: int = 1) -> None:
        """Increment the session count."""
        self.session_count += delta
        self.touch()
    
    def decrement_session_count(self, delta: int = 1) -> None:
        """Decrement the session count."""
        self.session_count = max(0, self.session_count - delta)
        self.touch()
    
    def increment_document_count(self, delta: int = 1) -> None:
        """Increment the document count."""
        self.document_count += delta
        self.touch()
    
    def decrement_document_count(self, delta: int = 1) -> None:
        """Decrement the document count."""
        self.document_count = max(0, self.document_count - delta)
        self.touch()


