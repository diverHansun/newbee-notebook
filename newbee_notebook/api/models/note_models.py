"""Pydantic models for note APIs."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CreateNoteRequest(BaseModel):
    """Request body for creating a note."""

    notebook_id: str = Field(..., min_length=1)
    title: str = ""
    content: str = ""
    document_ids: list[str] = Field(default_factory=list)


class UpdateNoteRequest(BaseModel):
    """Request body for partial note updates."""

    title: Optional[str] = None
    content: Optional[str] = None


class TagDocumentRequest(BaseModel):
    """Request body for attaching a document to a note."""

    document_id: str = Field(..., min_length=1)


class NoteResponse(BaseModel):
    """Full note response."""

    note_id: str
    notebook_id: str
    title: str
    content: str
    document_ids: list[str]
    mark_ids: list[str]
    created_at: datetime
    updated_at: datetime


class NoteListItemResponse(BaseModel):
    """Compact note summary for notebook listing."""

    note_id: str
    notebook_id: str
    title: str
    document_ids: list[str]
    mark_count: int
    created_at: datetime
    updated_at: datetime


class NoteListResponse(BaseModel):
    """List response for notes."""

    notes: list[NoteListItemResponse]
    total: int
