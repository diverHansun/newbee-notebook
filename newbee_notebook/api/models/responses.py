"""
Newbee Notebook - API Response Models
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
    include_ec_context: bool = False
    created_at: datetime
    updated_at: datetime


class SessionListResponse(BaseModel):
    """Response model for session list."""
    data: List[SessionResponse]
    pagination: PaginationInfo


class MessageResponse(BaseModel):
    """Response model for a single message."""
    message_id: int
    session_id: str
    mode: str
    role: str
    content: str
    created_at: datetime


class MessageListResponse(BaseModel):
    """Response model for paginated session messages."""
    data: List[MessageResponse]
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
    processing_stage: Optional[str] = None
    stage_updated_at: Optional[datetime] = None
    processing_meta: Optional[dict[str, Any]] = None
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


class UploadFailureResponse(BaseModel):
    """A failed file upload item."""

    filename: str
    reason: str


class UploadDocumentsResponse(BaseModel):
    """Response model for batch library upload."""

    documents: List[DocumentResponse]
    total: int
    failed: List[UploadFailureResponse]


class NotebookDocumentsAddItem(BaseModel):
    """Added document info for notebook association."""

    document_id: str
    title: str
    status: str
    action: str
    processing_stage: Optional[str] = None


class NotebookDocumentsProblemItem(BaseModel):
    """Skipped/failed document info for notebook association."""

    document_id: str
    reason: str


class NotebookDocumentsAddResponse(BaseModel):
    """Response model for adding documents to notebook."""

    notebook_id: str
    added: List[NotebookDocumentsAddItem]
    skipped: List[NotebookDocumentsProblemItem]
    failed: List[NotebookDocumentsProblemItem]


class NotebookDocumentListItemResponse(BaseModel):
    """Document item in notebook listing."""

    document_id: str
    title: str
    status: str
    content_type: str
    file_size: int = 0
    page_count: int = 0
    chunk_count: int = 0
    processing_stage: Optional[str] = None
    stage_updated_at: Optional[datetime] = None
    processing_meta: Optional[dict[str, Any]] = None
    created_at: datetime
    added_at: Optional[datetime] = None


class NotebookDocumentListResponse(BaseModel):
    """Response model for notebook associated document list."""

    data: List[NotebookDocumentListItemResponse]
    pagination: PaginationInfo


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


class MCPServerStatusResponse(BaseModel):
    """Response model for a single MCP server status item."""

    name: str
    transport: str
    enabled: bool
    connection_status: str
    tool_count: int
    error_message: Optional[str] = None


class MCPServersStatusResponse(BaseModel):
    """Response model for MCP server status listing."""

    mcp_enabled: bool
    servers: List[MCPServerStatusResponse]


class UpdateSettingResponse(BaseModel):
    """Response model for a key/value settings update."""

    key: str
    value: str


