"""
MediMind Agent - API Response Models
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class PaginationInfo(BaseModel):
    """Pagination information for list responses."""
    total: int = Field(..., description="Total number of items")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Number of items skipped")
    has_next: bool = Field(..., description="Whether there are more items")
    has_prev: bool = Field(..., description="Whether there are previous items")


class ErrorResponse(BaseModel):
    """Standard error response format."""
    error_code: str = Field(..., description="Error code (Exxxx format)")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict] = Field(None, description="Additional error details")


# =============================================================================
# Library Responses
# =============================================================================

class LibraryResponse(BaseModel):
    """Response model for library info."""
    library_id: str
    document_count: int
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Notebook Responses
# =============================================================================

class NotebookResponse(BaseModel):
    """Response model for a single notebook."""
    notebook_id: str
    title: str
    description: Optional[str]
    session_count: int
    document_count: int
    created_at: datetime
    updated_at: datetime


class NotebookListResponse(BaseModel):
    """Response model for notebook list."""
    data: List[NotebookResponse]
    pagination: PaginationInfo


# =============================================================================
# Session Responses
# =============================================================================

class SessionResponse(BaseModel):
    """Response model for a single session."""
    session_id: str
    notebook_id: str
    title: Optional[str]
    message_count: int
    created_at: datetime
    updated_at: datetime


class SessionListResponse(BaseModel):
    """Response model for session list."""
    data: List[SessionResponse]
    pagination: PaginationInfo


# =============================================================================
# Document Responses
# =============================================================================

class DocumentResponse(BaseModel):
    """Response model for a single document."""
    document_id: str
    title: str
    content_type: str
    status: str
    library_id: Optional[str]
    notebook_id: Optional[str]
    page_count: int
    chunk_count: int
    file_size: int
    content_path: Optional[str] = None
    content_format: Optional[str] = None
    content_size: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """Response model for document list."""
    data: List[DocumentResponse]
    pagination: PaginationInfo


class DocumentContentResponse(BaseModel):
    """Response model for document content."""
    document_id: str
    title: str
    format: str
    content: str
    page_count: int
    content_size: int


# =============================================================================
# Reference Responses
# =============================================================================

class NotebookDocumentRefResponse(BaseModel):
    """Response model for notebook-document reference."""
    reference_id: str
    notebook_id: str
    document_id: str
    document_title: Optional[str] = None
    created_at: datetime


