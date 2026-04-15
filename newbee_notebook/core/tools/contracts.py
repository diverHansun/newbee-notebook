"""Unified runtime tool contracts for the batch-2 agent runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass(frozen=True)
class SourceItem:
    document_id: str
    chunk_id: str
    title: str
    text: str
    score: float = 0.0
    source_type: str = "retrieval"


@dataclass(frozen=True)
class ToolQualityMeta:
    scope_used: str
    search_type: str
    result_count: int
    max_score: float | None
    quality_band: str
    scope_relaxation_recommended: bool


@dataclass(frozen=True)
class ImageResult:
    image_id: str
    storage_key: str
    prompt: str
    provider: str
    model: str
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class ToolCallResult:
    content: str
    sources: list[SourceItem] = field(default_factory=list)
    images: list[ImageResult] = field(default_factory=list)
    quality_meta: ToolQualityMeta | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


ToolExecutor = Callable[[dict[str, Any]], Awaitable[ToolCallResult]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    execute: ToolExecutor
