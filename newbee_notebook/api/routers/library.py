"""
Newbee Notebook - Library Router

Handles Library-related API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from newbee_notebook.api.models.responses import (
    LibraryResponse,
    DocumentResponse,
    DocumentListResponse,
    PaginationInfo,
)
from newbee_notebook.api.dependencies import get_library_service
from newbee_notebook.api.dependencies import get_document_service
from newbee_notebook.application.services.library_service import LibraryService
from newbee_notebook.application.services.document_service import DocumentService
from newbee_notebook.domain.value_objects.document_status import DocumentStatus


router = APIRouter(prefix="/library")


def _to_document_response(doc) -> DocumentResponse:
    """Convert domain Document to response model."""
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


@router.get("", response_model=LibraryResponse)
async def get_library(service: LibraryService = Depends(get_library_service)):
    """
    Get Library information.
    
    Returns the global Library with document count.
    """
    library = await service.get_or_create()
    # Document count is derived; compute via repository
    doc_count = await service.document_repo.count_by_library()
    return LibraryResponse(
        library_id=library.library_id,
        document_count=doc_count,
        created_at=library.created_at,
        updated_at=library.updated_at,
    )


@router.get("/documents", response_model=DocumentListResponse)
async def list_library_documents(
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    status: Optional[str] = Query(None, description="Filter by status"),
    service: LibraryService = Depends(get_library_service),
):
    """
    List documents in the Library.
    
    Args:
        limit: Maximum number of documents to return.
        offset: Number of documents to skip.
        status: Optional status filter (uploaded, pending, processing, converted, completed, failed).
        
    Returns:
        List of documents with pagination info.
    """
    status_enum = None
    if status:
        try:
            status_enum = DocumentStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status filter")

    documents, total = await service.list_documents(
        limit=limit, offset=offset, status=status_enum
    )

    return DocumentListResponse(
        data=[_to_document_response(d) for d in documents],
        pagination=PaginationInfo(
            total=total,
            limit=limit,
            offset=offset,
            has_next=offset + limit < total,
            has_prev=offset > 0,
        ),
    )


@router.delete("/documents/{document_id}")
async def delete_library_document(
    document_id: str,
    force: bool = Query(False),
    service: DocumentService = Depends(get_document_service),
):
    """
    Delete a document from the Library.
    
    If the document is referenced by Notebooks, requires force=true.
    
    Args:
        document_id: Document unique identifier.
        force: Set to true to force deletion even if referenced.
        
    Returns:
        Deletion confirmation.
        
    Raises:
        404: Document not found.
    """
    try:
        if force:
            await service.force_delete_document(document_id)
        else:
            await service.delete_document(document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")

    return {"message": "Document deleted", "document_id": document_id}


