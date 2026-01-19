"""
MediMind Agent - Documents Router

Handles document registration, listing, retrieval, and deletion.
File upload/processing is intentionally minimal; will be extended.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, UploadFile, File

from medimind_agent.api.models.requests import UploadDocumentRequest
from medimind_agent.api.models.responses import (
    DocumentResponse,
    DocumentListResponse,
    PaginationInfo,
)
from medimind_agent.api.dependencies import get_document_service
from medimind_agent.application.services.document_service import DocumentService, DocumentOwnershipError
from medimind_agent.domain.value_objects.document_status import DocumentStatus
from medimind_agent.domain.value_objects.document_type import DocumentType


router = APIRouter(prefix="/documents")


def _to_response(doc) -> DocumentResponse:
    return DocumentResponse(
        document_id=doc.document_id,
        title=doc.title,
        content_type=doc.content_type.value,
        status=doc.status.value,
        library_id=doc.library_id,
        notebook_id=doc.notebook_id,
        page_count=doc.page_count,
        chunk_count=doc.chunk_count,
        file_size=doc.file_size,
        error_message=doc.error_message,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.post("/library", response_model=DocumentResponse, status_code=201)
async def upload_to_library(
    request: UploadDocumentRequest,
    service: DocumentService = Depends(get_document_service),
):
    """
    Register a document to the Library.

    This endpoint currently accepts metadata only. File handling/processing
    will be added later; file_path/url can be prefilled.
    """
    doc = await service.create_library_document(
        title=request.title,
        content_type=request.content_type,
        file_path=request.file_path or "",
        url=request.url,
        file_size=request.file_size or 0,
    )
    return _to_response(doc)


@router.post("/notebooks/{notebook_id}", response_model=DocumentResponse, status_code=201)
async def upload_to_notebook(
    notebook_id: str = Path(..., description="Notebook ID"),
    request: UploadDocumentRequest = None,
    service: DocumentService = Depends(get_document_service),
):
    """Register a document owned by a Notebook."""
    try:
        doc = await service.create_notebook_document(
            notebook_id=notebook_id,
            title=request.title,
            content_type=request.content_type,
            file_path=request.file_path or "",
            url=request.url,
            file_size=request.file_size or 0,
        )
        return _to_response(doc)
    except DocumentOwnershipError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/library/upload", response_model=DocumentResponse, status_code=201)
async def upload_file_to_library(
    file: UploadFile = File(...),
    service: DocumentService = Depends(get_document_service),
):
    doc = await service.save_upload_and_register(
        upload=file,
        to_library=True,
    )
    return _to_response(doc)


@router.post("/notebooks/{notebook_id}/upload", response_model=DocumentResponse, status_code=201)
async def upload_file_to_notebook(
    notebook_id: str,
    file: UploadFile = File(...),
    service: DocumentService = Depends(get_document_service),
):
    try:
        doc = await service.save_upload_and_register(
            upload=file,
            to_library=False,
            notebook_id=notebook_id,
        )
        return _to_response(doc)
    except DocumentOwnershipError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    service: DocumentService = Depends(get_document_service),
):
    doc = await service.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _to_response(doc)


@router.get("/library", response_model=DocumentListResponse)
async def list_library_documents(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, description="Filter by status"),
    service: DocumentService = Depends(get_document_service),
):
    if status:
        try:
            status_enum = DocumentStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status filter")
    else:
        status_enum = None
    docs, total = await service.list_library_documents(limit=limit, offset=offset, status=status_enum)
    return DocumentListResponse(
        data=[_to_response(d) for d in docs],
        pagination=PaginationInfo(
            total=total,
            limit=limit,
            offset=offset,
            has_next=offset + limit < total,
            has_prev=offset > 0,
        ),
    )


@router.get("/notebooks/{notebook_id}", response_model=DocumentListResponse)
async def list_notebook_documents(
    notebook_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: DocumentService = Depends(get_document_service),
):
    try:
        docs, total = await service.list_notebook_documents(notebook_id, limit=limit, offset=offset)
    except DocumentOwnershipError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return DocumentListResponse(
        data=[_to_response(d) for d in docs],
        pagination=PaginationInfo(
            total=total,
            limit=limit,
            offset=offset,
            has_next=offset + limit < total,
            has_prev=offset > 0,
        ),
    )


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    confirm: bool = Query(False, description="Force delete if referenced"),
    service: DocumentService = Depends(get_document_service),
):
    try:
        await service.delete_document(document_id, force=confirm)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"message": "Document deleted", "document_id": document_id}
