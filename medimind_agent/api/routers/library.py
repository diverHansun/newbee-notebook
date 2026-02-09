"""
MediMind Agent - Library Router

Handles Library-related API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from medimind_agent.api.models.responses import (
    LibraryResponse,
    DocumentResponse,
    DocumentListResponse,
    PaginationInfo,
)
from medimind_agent.api.dependencies import get_library_service
from medimind_agent.api.dependencies import get_document_service
from medimind_agent.application.services.library_service import LibraryService
from medimind_agent.application.services.document_service import DocumentService
from medimind_agent.domain.value_objects.document_status import DocumentStatus


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
        status: Optional status filter (uploaded, pending, processing, completed, failed).
        
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
        409: Document is referenced (without force=true).
    """
    try:
        await service.delete_document(document_id, force=force)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {"message": "Document deleted", "document_id": document_id}


