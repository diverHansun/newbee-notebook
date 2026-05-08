"""
Newbee Notebook - API Request Models
"""

from typing import Optional, List, Literal

from pydantic import BaseModel, Field, field_validator

from newbee_notebook.domain.value_objects.document_type import DocumentType


class CreateNotebookRequest(BaseModel):
    """Request model for creating a notebook."""

    title: str = Field(..., min_length=1, max_length=500, description="Notebook title")
    description: Optional[str] = Field(
        None, max_length=2000, description="Optional description"
    )


class UpdateNotebookRequest(BaseModel):
    """Request model for updating a notebook."""

    title: Optional[str] = Field(
        None, min_length=1, max_length=500, description="New title"
    )
    description: Optional[str] = Field(
        None, max_length=2000, description="New description"
    )


class CreateSessionRequest(BaseModel):
    """Request model for creating a session."""

    title: Optional[str] = Field(
        None, max_length=500, description="Optional session title"
    )
    include_ec_context: bool = Field(
        False,
        description="Whether Agent/Ask requests should include recent Explain/Conclude context by default.",
    )


class CreateReferenceRequest(BaseModel):
    """Legacy request model for creating a notebook-document reference."""

    document_id: str = Field(..., description="ID of the Library document to reference")


class UploadDocumentRequest(BaseModel):
    """Legacy metadata-only document creation request."""

    title: str = Field(..., min_length=1, max_length=500, description="Document title")
    content_type: DocumentType = Field(
        DocumentType.PDF, description="Document type/extension"
    )
    url: Optional[str] = Field(None, description="Optional source URL")
    file_path: Optional[str] = Field(
        None, description="Server-side file path if already saved"
    )
    file_size: Optional[int] = Field(0, ge=0, description="File size in bytes")


class AddNotebookDocumentsRequest(BaseModel):
    """Request model for adding existing Library documents to a notebook."""

    document_ids: List[str] = Field(..., description="Document IDs from Library")


class ChatContext(BaseModel):
    """Selected-text context sent from frontend."""

    selected_text: Optional[str] = Field(None, description="User selected text snippet")
    chunk_id: Optional[str] = Field(
        None, description="Chunk identifier in vector store"
    )
    document_id: Optional[str] = Field(
        None, description="Document id owning the selection"
    )
    page_number: Optional[int] = Field(None, description="Page number if available")


class ChatRequest(BaseModel):
    """Request model for the /chat and /chat/stream endpoints."""

    message: str = Field(..., min_length=1, description="User message")
    mode: Literal["chat", "agent", "ask", "explain", "conclude"] = Field(
        "agent",
        description="Interaction mode. 'chat' remains accepted as a compatibility alias for 'agent'.",
    )
    session_id: Optional[str] = Field(None, description="Session ID (optional)")
    context: Optional[ChatContext] = Field(None, description="Selected text context")
    include_ec_context: Optional[bool] = Field(
        None,
        description="Optional override for including recent explain/conclude context in agent/ask requests.",
    )
    source_document_ids: Optional[list[str]] = Field(
        None,
        description="Optional document IDs to limit retrieval scope. None uses all notebook documents.",
    )
    image_ids: list[str] = Field(
        default_factory=list,
        description="Uploaded chat image IDs attached to this user turn.",
    )
    agent_policy: Literal["default", "yolo"] = Field(
        "default",
        description=(
            "Agent execution policy. 'default' asks for sensitive actions; "
            "'yolo' skips permission prompts while keeping sandbox."
        ),
    )
    lang: Literal["en", "zh"] = Field(
        "en",
        description="Language for system prompt. Defaults to 'en'.",
    )

    @field_validator("message")
    @classmethod
    def _message_must_contain_text(cls, value: str) -> str:
        if not str(value or "").strip():
            raise ValueError("message must contain text")
        return value

    @field_validator("image_ids")
    @classmethod
    def _normalize_image_ids(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for image_id in value or []:
            cleaned = str(image_id or "").strip()
            if cleaned and cleaned not in normalized:
                normalized.append(cleaned)
        return normalized


class UpdateSettingRequest(BaseModel):
    """Minimal key/value request model for runtime settings."""

    key: str = Field(..., min_length=1, description="Setting key")
    value: str = Field(..., description="Setting value")
