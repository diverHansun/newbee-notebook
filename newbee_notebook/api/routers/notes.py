"""Notes API router."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response

from newbee_notebook.api.dependencies import get_note_service
from newbee_notebook.api.models.note_models import (
    CreateNoteRequest,
    NoteListItemResponse,
    NoteListResponse,
    NoteResponse,
    TagDocumentRequest,
    UpdateNoteRequest,
)
from newbee_notebook.application.services.note_service import NoteNotFoundError, NoteService


router = APIRouter()


def _to_note_response(note) -> NoteResponse:
    return NoteResponse(
        note_id=note.note_id,
        notebook_id=note.notebook_id,
        title=note.title,
        content=note.content,
        document_ids=list(note.document_ids),
        mark_ids=list(note.mark_ids),
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


def _to_note_list_item(note) -> NoteListItemResponse:
    return NoteListItemResponse(
        note_id=note.note_id,
        notebook_id=note.notebook_id,
        title=note.title,
        document_ids=list(note.document_ids),
        mark_count=len(note.mark_ids),
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.post("/notes", response_model=NoteResponse, status_code=201)
async def create_note(
    request: CreateNoteRequest,
    service: NoteService = Depends(get_note_service),
):
    try:
        note = await service.create(
            notebook_id=request.notebook_id,
            title=request.title,
            content=request.content,
            document_ids=request.document_ids,
        )
        return _to_note_response(note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/notes", response_model=NoteListResponse)
async def list_all_notes(
    document_id: Optional[str] = Query(None, description="Filter by document ID"),
    sort_by: str = Query("updated_at", description="Sort field: created_at or updated_at"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    service: NoteService = Depends(get_note_service),
):
    notes = await service.list_all(
        document_id=document_id,
        sort_by=sort_by,
        order=order,
    )
    return NoteListResponse(
        notes=[_to_note_list_item(note) for note in notes],
        total=len(notes),
    )


@router.get("/notebooks/{notebook_id}/notes", response_model=NoteListResponse)
async def list_notes(
    notebook_id: str = Path(..., description="Notebook ID"),
    document_id: Optional[str] = Query(None, description="Optional document filter"),
    service: NoteService = Depends(get_note_service),
):
    if document_id is None:
        notes = await service.list_by_notebook(notebook_id)
    else:
        notes = await service.list_by_notebook(notebook_id, document_id=document_id)
    return NoteListResponse(
        notes=[_to_note_list_item(note) for note in notes],
        total=len(notes),
    )


@router.get("/notes/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: str = Path(..., description="Note ID"),
    service: NoteService = Depends(get_note_service),
):
    try:
        return _to_note_response(await service.get_or_raise(note_id))
    except NoteNotFoundError:
        raise HTTPException(status_code=404, detail="Note not found")


@router.patch("/notes/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: str = Path(..., description="Note ID"),
    request: UpdateNoteRequest = None,
    service: NoteService = Depends(get_note_service),
):
    try:
        note = await service.update(
            note_id,
            title=request.title if request else None,
            content=request.content if request else None,
        )
        return _to_note_response(note)
    except NoteNotFoundError:
        raise HTTPException(status_code=404, detail="Note not found")


@router.delete("/notes/{note_id}", status_code=204)
async def delete_note(
    note_id: str = Path(..., description="Note ID"),
    service: NoteService = Depends(get_note_service),
):
    try:
        await service.delete(note_id)
    except NoteNotFoundError:
        raise HTTPException(status_code=404, detail="Note not found")
    return Response(status_code=204)


@router.post("/notes/{note_id}/documents", status_code=204)
async def add_note_document(
    note_id: str = Path(..., description="Note ID"),
    request: TagDocumentRequest = None,
    service: NoteService = Depends(get_note_service),
):
    try:
        await service.add_document_tag(note_id, request.document_id)
    except NoteNotFoundError:
        raise HTTPException(status_code=404, detail="Note not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return Response(status_code=204)


@router.delete("/notes/{note_id}/documents/{document_id}", status_code=204)
async def remove_note_document(
    note_id: str = Path(..., description="Note ID"),
    document_id: str = Path(..., description="Document ID"),
    service: NoteService = Depends(get_note_service),
):
    try:
        await service.remove_document_tag(note_id, document_id)
    except NoteNotFoundError:
        raise HTTPException(status_code=404, detail="Note not found")
    return Response(status_code=204)
