"""Pydantic models for video and Bilibili auth APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field


class SummarizeRequest(BaseModel):
    url_or_id: str = Field(
        ...,
        min_length=1,
        validation_alias=AliasChoices("url_or_id", "url_or_bvid"),
    )
    notebook_id: str | None = None
    lang: Literal["zh", "en"] = "zh"


class AssociateNotebookRequest(BaseModel):
    notebook_id: str = Field(..., min_length=1)


class TagDocumentRequest(BaseModel):
    document_id: str = Field(..., min_length=1)


class VideoSummaryResponse(BaseModel):
    summary_id: str
    notebook_id: str | None
    platform: str
    video_id: str
    source_url: str
    title: str
    cover_url: str | None = None
    duration_seconds: int
    uploader_name: str
    uploader_id: str
    summary_content: str
    status: str
    metadata_ready: bool = True
    error_message: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    stats: dict | None = None
    transcript_source: str = ""
    transcript_path: str | None = None
    created_at: datetime
    updated_at: datetime


class VideoSummaryListItemResponse(BaseModel):
    summary_id: str
    notebook_id: str | None
    platform: str
    video_id: str
    title: str
    cover_url: str | None = None
    duration_seconds: int
    uploader_name: str
    status: str
    metadata_ready: bool = True
    created_at: datetime
    updated_at: datetime


class VideoSummaryListResponse(BaseModel):
    summaries: list[VideoSummaryListItemResponse]
    total: int


class VideoInfoResponse(BaseModel):
    video_id: str
    source_url: str
    title: str
    description: str = ""
    cover_url: str | None = None
    duration_seconds: int
    uploader_name: str
    uploader_id: str
    stats: dict | None = None


class VideoSearchResponse(BaseModel):
    results: list[dict] = Field(default_factory=list)
    total: int


class VideoListResponse(BaseModel):
    results: list[dict] = Field(default_factory=list)
    total: int


class AuthStatusResponse(BaseModel):
    logged_in: bool
