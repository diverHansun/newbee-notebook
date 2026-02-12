"""
Newbee Notebook - Documents Router

Library-first document APIs.
"""

from typing import Optional, List
import mimetypes

from fastapi import APIRouter, Depends, HTTPException, Query, Path, UploadFile, File
from fastapi.responses import FileResponse

from newbee_notebook.api.models.responses import (
    DocumentResponse,
    DocumentListResponse,
    PaginationInfo,
    DocumentContentResponse,
    UploadDocumentsResponse,
    UploadFailureResponse,
)
from newbee_notebook.api.dependencies import get_document_service
from newbee_notebook.application.services.document_service import DocumentService
from newbee_notebook.domain.value_objects.document_status import DocumentStatus


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
        content_path=doc.content_path,
        content_format=doc.content_format,
        content_size=doc.content_size,
        error_message=doc.error_message,
        processing_stage=doc.processing_stage,
        stage_updated_at=doc.stage_updated_at,
        processing_meta=doc.processing_meta,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.post("/library", deprecated=True)
async def upload_to_library_metadata_deprecated():
    """Deprecated metadata-only endpoint."""
    raise HTTPException(
        status_code=410,
        detail=(
            "This endpoint is deprecated. Use POST /api/v1/documents/library/upload "
            "with files and then POST /api/v1/notebooks/{notebook_id}/documents."
        ),
    )


@router.post("/notebooks/{notebook_id}", deprecated=True)
async def upload_to_notebook_metadata_deprecated():
    """Deprecated notebook-owned document endpoint."""
    raise HTTPException(
        status_code=410,
        detail=(
            "Notebook direct upload is deprecated. Upload to Library first via "
            "POST /api/v1/documents/library/upload, then associate via "
            "POST /api/v1/notebooks/{notebook_id}/documents."
        ),
    )


@router.post("/library/upload", response_model=UploadDocumentsResponse, status_code=201)
async def upload_files_to_library(
    files: List[UploadFile] = File(...),
    service: DocumentService = Depends(get_document_service),
):
    """Batch upload files to Library. Upload does not trigger processing."""
    documents, failed = await service.upload_to_library(files)
    return UploadDocumentsResponse(
        documents=[_to_response(doc) for doc in documents],
        total=len(documents),
        failed=[
            UploadFailureResponse(filename=item["filename"], reason=item["reason"])
            for item in failed
        ],
    )


@router.post("/notebooks/{notebook_id}/upload", deprecated=True)
async def upload_file_to_notebook_deprecated(
    notebook_id: str,
):
    """Deprecated notebook direct upload endpoint."""
    raise HTTPException(
        status_code=410,
        detail=(
            "This endpoint is deprecated. Use POST /api/v1/documents/library/upload "
            "and POST /api/v1/notebooks/{notebook_id}/documents instead."
        ),
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str = Path(..., description="Document ID", pattern="^[0-9a-fA-F-]{36}$"),
    service: DocumentService = Depends(get_document_service),
):
    doc = await service.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _to_response(doc)


@router.get("/{document_id}/content", response_model=DocumentContentResponse)
async def get_document_content(
    document_id: str = Path(..., description="Document ID", pattern="^[0-9a-fA-F-]{36}$"),
    format: str = Query("markdown", pattern="^(markdown|text)$"),
    service: DocumentService = Depends(get_document_service),
):
    try:
        doc, content = await service.get_document_content(document_id, format=format)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return DocumentContentResponse(
        document_id=doc.document_id,
        title=doc.title,
        format=format,
        content=content,
        page_count=doc.page_count,
        content_size=doc.content_size or len(content.encode("utf-8")),
    )


@router.get("/{document_id}/download")
async def download_document(
    document_id: str = Path(..., description="Document ID", pattern="^[0-9a-fA-F-]{36}$"),
    service: DocumentService = Depends(get_document_service),
):
    """Download original uploaded file."""
    try:
        file_path, filename = await service.get_download_path(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return FileResponse(path=file_path, filename=filename, media_type="application/octet-stream")


@router.get("/{document_id}/assets/{asset_path:path}")
async def get_document_asset(
    document_id: str = Path(..., description="Document ID", pattern="^[0-9a-fA-F-]{36}$"),
    asset_path: str = Path(..., description="Relative asset path under assets/"),
    service: DocumentService = Depends(get_document_service),
):
    """Serve generated document assets (images/json) for frontend rendering."""
    try:
        file_path = await service.get_asset_path(document_id, asset_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(path=file_path, media_type=media_type or "application/octet-stream")


@router.get("/library", response_model=DocumentListResponse)
async def list_library_documents(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, description="Filter by status"),
    service: DocumentService = Depends(get_document_service),
):
    status_enum = None
    if status:
        try:
            status_enum = DocumentStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status filter")

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


@router.get("/notebooks/{notebook_id}", deprecated=True)
async def list_notebook_documents_deprecated(
    notebook_id: str,
):
    """Deprecated endpoint replaced by /notebooks/{notebook_id}/documents."""
    raise HTTPException(
        status_code=410,
        detail="This endpoint is deprecated. Use GET /api/v1/notebooks/{notebook_id}/documents.",
    )


@router.delete("/{document_id}")
async def delete_document(
    document_id: str = Path(..., description="Document ID", pattern="^[0-9a-fA-F-]{36}$"),
    force: bool = Query(
        False,
        description="Deprecated parameter. This endpoint always performs soft delete.",
    ),
    service: DocumentService = Depends(get_document_service),
):
    try:
        _ = force  # compatibility no-op
        await service.delete_document(document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted", "document_id": document_id}
