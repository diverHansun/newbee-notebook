"""
Newbee Notebook - API Request Models
"""

from typing import Optional, List

from pydantic import BaseModel, Field

from newbee_notebook.domain.value_objects.document_type import DocumentType


class CreateNotebookRequest(BaseModel):
    """Request model for creating a notebook."""

    title: str = Field(..., min_length=1, max_length=500, description="Notebook title")
    description: Optional[str] = Field(None, max_length=2000, description="Optional description")


class UpdateNotebookRequest(BaseModel):
    """Request model for updating a notebook."""

    title: Optional[str] = Field(None, min_length=1, max_length=500, description="New title")
    description: Optional[str] = Field(None, max_length=2000, description="New description")


class CreateSessionRequest(BaseModel):
    """Request model for creating a session."""

    title: Optional[str] = Field(None, max_length=500, description="Optional session title")
    include_ec_context: bool = Field(
        False,
        description="Whether Chat/Ask requests should include recent Explain/Conclude context by default.",
    )


class CreateReferenceRequest(BaseModel):
    """Legacy request model for creating a notebook-document reference."""

    document_id: str = Field(..., description="ID of the Library document to reference")


class UploadDocumentRequest(BaseModel):
    """Legacy metadata-only document creation request."""

    title: str = Field(..., min_length=1, max_length=500, description="Document title")
    content_type: DocumentType = Field(DocumentType.PDF, description="Document type/extension")
    url: Optional[str] = Field(None, description="Optional source URL")
    file_path: Optional[str] = Field(None, description="Server-side file path if already saved")
    file_size: Optional[int] = Field(0, ge=0, description="File size in bytes")


class AddNotebookDocumentsRequest(BaseModel):
    """Request model for adding existing Library documents to a notebook."""

    document_ids: List[str] = Field(..., description="Document IDs from Library")


class ChatContext(BaseModel):
    """Selected-text context sent from frontend."""

    selected_text: Optional[str] = Field(None, description="User selected text snippet")
    chunk_id: Optional[str] = Field(None, description="Chunk identifier in vector store")
    document_id: Optional[str] = Field(None, description="Document id owning the selection")
    page_number: Optional[int] = Field(None, description="Page number if available")
