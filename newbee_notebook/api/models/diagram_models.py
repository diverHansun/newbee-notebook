"""Pydantic models for diagram APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DiagramResponse(BaseModel):
    """Full diagram metadata response."""

    diagram_id: str
    notebook_id: str
    title: str
    diagram_type: str
    format: str
    document_ids: list[str]
    node_positions: Optional[dict[str, dict[str, float]]] = None
    created_at: datetime
    updated_at: datetime


class CreateDiagramRequest(BaseModel):
    """Request body for creating a diagram."""

    model_config = ConfigDict(extra="forbid")

    notebook_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    diagram_type: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    document_ids: list[str] = Field(default_factory=list)


class DiagramListResponse(BaseModel):
    """Diagram list response."""

    diagrams: list[DiagramResponse]
    total: int


class UpdateDiagramPositionsRequest(BaseModel):
    """Request body for node position update."""

    positions: dict[str, dict[str, float]] = Field(default_factory=dict)
