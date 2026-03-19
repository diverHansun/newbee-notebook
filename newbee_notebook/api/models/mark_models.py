"""Pydantic models for mark APIs."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CreateMarkRequest(BaseModel):
    """Request body for creating a mark."""

    anchor_text: str = Field(..., min_length=1, max_length=500)
    char_offset: int = Field(..., ge=0)
    context_text: Optional[str] = None


class MarkResponse(BaseModel):
    """Mark detail response."""

    mark_id: str
    document_id: str
    anchor_text: str
    char_offset: int
    context_text: Optional[str]
    created_at: datetime
    updated_at: datetime


class MarkListResponse(BaseModel):
    """List response for marks."""

    marks: list[MarkResponse]
    total: int


class MarkCountResponse(BaseModel):
    """Count response for marks."""

    count: int
