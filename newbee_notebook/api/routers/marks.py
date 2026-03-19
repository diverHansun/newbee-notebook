"""Marks API router."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response

from newbee_notebook.api.dependencies import get_mark_service
from newbee_notebook.api.models.mark_models import (
    CreateMarkRequest,
    MarkCountResponse,
    MarkListResponse,
    MarkResponse,
)
from newbee_notebook.application.services.mark_service import (
    MarkDocumentNotFoundError,
    MarkDocumentNotReadyError,
    MarkNotFoundError,
    MarkService,
)


router = APIRouter()


def _to_response(mark) -> MarkResponse:
    return MarkResponse(
        mark_id=mark.mark_id,
        document_id=mark.document_id,
        anchor_text=mark.anchor_text,
        char_offset=mark.char_offset,
        context_text=mark.context_text,
        created_at=mark.created_at,
        updated_at=mark.updated_at,
    )


@router.post("/documents/{document_id}/marks", response_model=MarkResponse, status_code=201)
async def create_mark(
    document_id: str = Path(..., description="Document ID"),
    request: CreateMarkRequest = None,
    service: MarkService = Depends(get_mark_service),
):
    try:
        mark = await service.create(
            document_id=document_id,
            anchor_text=request.anchor_text,
            char_offset=request.char_offset,
            context_text=request.context_text,
        )
        return _to_response(mark)
    except MarkDocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except MarkDocumentNotReadyError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/documents/{document_id}/marks", response_model=MarkListResponse)
async def list_document_marks(
    document_id: str = Path(..., description="Document ID"),
    service: MarkService = Depends(get_mark_service),
):
    marks = await service.list_by_document(document_id)
    return MarkListResponse(marks=[_to_response(mark) for mark in marks], total=len(marks))


@router.get("/documents/{document_id}/marks/count", response_model=MarkCountResponse)
async def count_document_marks(
    document_id: str = Path(..., description="Document ID"),
    service: MarkService = Depends(get_mark_service),
):
    return MarkCountResponse(count=await service.count_by_document(document_id))


@router.get("/notebooks/{notebook_id}/marks", response_model=MarkListResponse)
async def list_notebook_marks(
    notebook_id: str = Path(..., description="Notebook ID"),
    document_id: Optional[str] = Query(None, description="Optional document filter"),
    service: MarkService = Depends(get_mark_service),
):
    marks = await service.list_by_notebook(notebook_id, document_id=document_id)
    return MarkListResponse(marks=[_to_response(mark) for mark in marks], total=len(marks))


@router.delete("/marks/{mark_id}", status_code=204)
async def delete_mark(
    mark_id: str = Path(..., description="Mark ID"),
    service: MarkService = Depends(get_mark_service),
):
    try:
        await service.delete(mark_id)
    except MarkNotFoundError:
        raise HTTPException(status_code=404, detail="Mark not found")
    return Response(status_code=204)
