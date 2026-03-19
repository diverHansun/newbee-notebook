"""Pydantic models for diagram APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


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


class DiagramListResponse(BaseModel):
    """Diagram list response."""

    diagrams: list[DiagramResponse]
    total: int


class UpdateDiagramPositionsRequest(BaseModel):
    """Request body for node position update."""

    positions: dict[str, dict[str, float]] = Field(default_factory=dict)
