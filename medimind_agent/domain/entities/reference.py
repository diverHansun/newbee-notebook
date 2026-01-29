"""
MediMind Agent - Reference Entities

Reference entities for document citations and notebook-document links.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from medimind_agent.domain.entities.base import Entity, generate_uuid


@dataclass
class NotebookDocumentRef(Entity):
    """
    Reference linking a Library document to a Notebook.
    
    This allows documents from Library to be used within a Notebook's context
    for RAG retrieval without copying the document.
    
    Attributes:
        reference_id: Unique identifier
        notebook_id: Target notebook ID
        document_id: Source document ID (from Library)
    """
    reference_id: str = field(default_factory=generate_uuid)
    notebook_id: str = ""
    document_id: str = ""


@dataclass
class Reference(Entity):
    """
    Reference entity - links AI responses to document sources.
    
    Used for citation tracking and source verification.
    The chunk_id stores the LlamaIndex node_id (no foreign key constraint).
    
    Attributes:
        reference_id: Unique identifier
        session_id: Session where this reference was created
        message_id: Message ID that contains this reference
        document_id: Source document ID
        chunk_id: LlamaIndex node_id (VARCHAR, no FK)
        quoted_text: The quoted text from the source
        context: Surrounding context
    """
    reference_id: str = field(default_factory=generate_uuid)
    session_id: str = ""
    message_id: int = 0
    document_id: Optional[str] = None
    chunk_id: str = ""  # LlamaIndex node_id
    quoted_text: Optional[str] = None
    context: Optional[str] = None
    document_title: Optional[str] = None
    is_source_deleted: bool = False


