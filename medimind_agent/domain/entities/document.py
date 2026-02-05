"""
MediMind Agent - Document Entity

A Document represents an uploaded file that has been processed.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from medimind_agent.domain.entities.base import Entity, generate_uuid
from medimind_agent.domain.value_objects.document_status import DocumentStatus
from medimind_agent.domain.value_objects.document_type import DocumentType


@dataclass
class Document(Entity):
    """
    Document entity - a file that has been uploaded and processed.
    
    Ownership rules:
    - library_id is set: belongs to Library
    - notebook_id is set: belongs to Notebook (exclusive document)
    - Only one of library_id or notebook_id can be set (enforced by DB constraint)
    
    Attributes:
        document_id: Unique identifier
        title: Document title
        content_type: Type of document (pdf, docx, etc.)
        file_path: Path to the stored file
        status: Processing status
        library_id: Library ID if belongs to Library
        notebook_id: Notebook ID if belongs to Notebook
        url: Source URL (for videos, web pages)
        page_count: Number of pages
        chunk_count: Number of chunks after processing
        file_size: File size in bytes
    """
    document_id: str = field(default_factory=generate_uuid)
    title: str = ""
    content_type: DocumentType = DocumentType.PDF
    file_path: str = ""
    status: DocumentStatus = DocumentStatus.PENDING
    library_id: Optional[str] = None
    notebook_id: Optional[str] = None
    url: Optional[str] = None
    page_count: int = 0
    chunk_count: int = 0
    file_size: int = 0
    content_path: Optional[str] = None
    content_format: str = "markdown"
    content_size: int = 0
    error_message: Optional[str] = None
    
    @property
    def is_library_document(self) -> bool:
        """Check if document belongs to Library."""
        return self.library_id is not None
    
    @property
    def is_notebook_document(self) -> bool:
        """Check if document belongs to a Notebook."""
        return self.notebook_id is not None
    
    @property
    def is_completed(self) -> bool:
        """Check if document processing is completed."""
        return self.status == DocumentStatus.COMPLETED
    
    @property
    def is_processing(self) -> bool:
        """Check if document is being processed."""
        return self.status == DocumentStatus.PROCESSING
    
    @property
    def is_failed(self) -> bool:
        """Check if document processing failed."""
        return self.status == DocumentStatus.FAILED
    
    def mark_processing(self) -> None:
        """Mark document as processing."""
        self.status = DocumentStatus.PROCESSING
        self.error_message = None
        self.touch()
    
    def mark_completed(
        self,
        chunk_count: int,
        page_count: int = 0,
        content_path: Optional[str] = None,
        content_size: Optional[int] = None,
        content_format: Optional[str] = None,
    ) -> None:
        """Mark document as completed and update content metadata."""
        self.status = DocumentStatus.COMPLETED
        self.chunk_count = chunk_count
        self.page_count = page_count
        if content_path is not None:
            self.content_path = content_path
        if content_size is not None:
            self.content_size = content_size
        if content_format is not None:
            self.content_format = content_format
        self.error_message = None
        self.touch()
    
    def mark_failed(self, error_message: Optional[str] = None) -> None:
        """Mark document as failed."""
        self.status = DocumentStatus.FAILED
        self.error_message = error_message
        self.touch()


