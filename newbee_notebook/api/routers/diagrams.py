"""Diagrams API router."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from fastapi.responses import PlainTextResponse

from newbee_notebook.api.dependencies import get_diagram_service
from newbee_notebook.api.models.diagram_models import (
    DiagramListResponse,
    DiagramResponse,
    UpdateDiagramPositionsRequest,
)
from newbee_notebook.application.services.diagram_service import (
    DiagramFormatMismatchError,
    DiagramNotFoundError,
    DiagramService,
)


router = APIRouter()


def _to_diagram_response(diagram) -> DiagramResponse:
    return DiagramResponse(
        diagram_id=diagram.diagram_id,
        notebook_id=diagram.notebook_id,
        title=diagram.title,
        diagram_type=diagram.diagram_type,
        format=diagram.format,
        document_ids=list(diagram.document_ids),
        node_positions=diagram.node_positions,
        created_at=diagram.created_at,
        updated_at=diagram.updated_at,
    )


@router.get("/diagrams", response_model=DiagramListResponse)
async def list_diagrams(
    notebook_id: str = Query(..., min_length=1, description="Notebook ID"),
    document_id: Optional[str] = Query(None, description="Optional document filter"),
    service: DiagramService = Depends(get_diagram_service),
):
    diagrams = await service.list_diagrams(notebook_id=notebook_id, document_id=document_id)
    return DiagramListResponse(
        diagrams=[_to_diagram_response(diagram) for diagram in diagrams],
        total=len(diagrams),
    )


@router.get("/diagrams/{diagram_id}", response_model=DiagramResponse)
async def get_diagram(
    diagram_id: str = Path(..., description="Diagram ID"),
    service: DiagramService = Depends(get_diagram_service),
):
    try:
        diagram = await service.get_diagram(diagram_id)
    except DiagramNotFoundError:
        raise HTTPException(status_code=404, detail="Diagram not found")
    return _to_diagram_response(diagram)


@router.get("/diagrams/{diagram_id}/content", response_class=PlainTextResponse)
async def get_diagram_content(
    diagram_id: str = Path(..., description="Diagram ID"),
    service: DiagramService = Depends(get_diagram_service),
):
    try:
        return await service.get_diagram_content(diagram_id)
    except DiagramNotFoundError:
        raise HTTPException(status_code=404, detail="Diagram not found")


@router.patch("/diagrams/{diagram_id}/positions", response_model=DiagramResponse)
async def update_diagram_positions(
    request: UpdateDiagramPositionsRequest,
    diagram_id: str = Path(..., description="Diagram ID"),
    service: DiagramService = Depends(get_diagram_service),
):
    try:
        diagram = await service.update_node_positions(diagram_id, request.positions)
    except DiagramNotFoundError:
        raise HTTPException(status_code=404, detail="Diagram not found")
    except DiagramFormatMismatchError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _to_diagram_response(diagram)


@router.delete("/diagrams/{diagram_id}", status_code=204)
async def delete_diagram(
    diagram_id: str = Path(..., description="Diagram ID"),
    service: DiagramService = Depends(get_diagram_service),
):
    try:
        await service.delete_diagram(diagram_id)
    except DiagramNotFoundError:
        raise HTTPException(status_code=404, detail="Diagram not found")
    return Response(status_code=204)
