"""API models for user-uploaded chat images."""

from __future__ import annotations

from newbee_notebook.api.models.timestamps import ApiTimestamp
from typing import List, Optional

from pydantic import BaseModel, Field


class ChatImageResponse(BaseModel):
    image_id: str
    session_id: str
    storage_key: str
    mime_type: str
    size_bytes: int
    width: Optional[int] = None
    height: Optional[int] = None
    sha256: str
    preview_url: str
    thumbnail_url: str
    created_at: ApiTimestamp


class ChatImageFailureResponse(BaseModel):
    filename: str
    reason: str


class ChatImageUploadResponse(BaseModel):
    images: List[ChatImageResponse] = Field(default_factory=list)
    total: int
    failed: List[ChatImageFailureResponse] = Field(default_factory=list)
