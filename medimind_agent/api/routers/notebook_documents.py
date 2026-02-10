"""Notebook document association router.

Library-first APIs:
- Add Library documents to Notebook
- List Notebook-associated documents
- Remove association
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from medimind_agent.api.dependencies import get_notebook_document_service
from medimind_agent.api.models.requests import AddNotebookDocumentsRequest
from medimind_agent.api.models.responses import (
    NotebookDocumentsAddResponse,
    NotebookDocumentsAddItem,
    NotebookDocumentsProblemItem,
    NotebookDocumentListItemResponse,
    NotebookDocumentListResponse,
    PaginationInfo,
)
from medimind_agent.application.services.notebook_document_service import (
    NotebookDocumentService,
    NotebookNotFoundError,
)
from medimind_agent.domain.value_objects.document_status import DocumentStatus


router = APIRouter(prefix="/notebooks/{notebook_id}/documents")


@router.post("", response_model=NotebookDocumentsAddResponse)
async def add_documents_to_notebook(
    notebook_id: str = Path(..., description="Notebook ID"),
    request: AddNotebookDocumentsRequest = None,
    service: NotebookDocumentService = Depends(get_notebook_document_service),
):
    """Add existing Library documents to notebook and trigger processing when needed."""
    if not request or not request.document_ids:
        raise HTTPException(status_code=400, detail="document_ids must not be empty")

    try:
        result = await service.add_documents(notebook_id, request.document_ids)
    except NotebookNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return NotebookDocumentsAddResponse(
        notebook_id=result.notebook_id,
        added=[
            NotebookDocumentsAddItem(
                document_id=doc.document_id,
                title=doc.title,
                status=doc.status.value,
                processing_stage=doc.processing_stage,
            )
            for doc in result.added
        ],
        skipped=[
            NotebookDocumentsProblemItem(document_id=item.document_id, reason=item.reason)
            for item in result.skipped
        ],
        failed=[
            NotebookDocumentsProblemItem(document_id=item.document_id, reason=item.reason)
            for item in result.failed
        ],
    )


@router.get("", response_model=NotebookDocumentListResponse)
async def list_notebook_documents(
    notebook_id: str = Path(..., description="Notebook ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, description="uploaded|pending|processing|completed|failed"),
    service: NotebookDocumentService = Depends(get_notebook_document_service),
):
    """List documents associated with notebook."""
    status_enum = None
    if status:
        try:
            status_enum = DocumentStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status filter")

    try:
        docs_with_added_at, total = await service.list_documents(
            notebook_id=notebook_id,
            limit=limit,
            offset=offset,
            status=status_enum,
        )
    except NotebookNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return NotebookDocumentListResponse(
        data=[
            NotebookDocumentListItemResponse(
                document_id=doc.document_id,
                title=doc.title,
                status=doc.status.value,
                content_type=doc.content_type.value,
                file_size=doc.file_size,
                page_count=doc.page_count,
                chunk_count=doc.chunk_count,
                processing_stage=doc.processing_stage,
                stage_updated_at=doc.stage_updated_at,
                processing_meta=doc.processing_meta,
                created_at=doc.created_at,
                added_at=added_at,
            )
            for doc, added_at in docs_with_added_at
        ],
        pagination=PaginationInfo(
            total=total,
            limit=limit,
            offset=offset,
            has_next=offset + limit < total,
            has_prev=offset > 0,
        ),
    )


@router.delete("/{document_id}", status_code=204)
async def remove_document_from_notebook(
    notebook_id: str = Path(..., description="Notebook ID"),
    document_id: str = Path(..., description="Document ID"),
    service: NotebookDocumentService = Depends(get_notebook_document_service),
):
    """Remove notebook-document association without deleting source document."""
    try:
        await service.remove_document(notebook_id, document_id)
    except NotebookNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
