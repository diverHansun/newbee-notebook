"""
Admin management endpoints for document processing and index monitoring.
"""

from typing import Optional, Dict
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from medimind_agent.api.dependencies import (
    get_document_repo,
    get_document_service,
)
from medimind_agent.domain.value_objects.document_status import DocumentStatus
from medimind_agent.infrastructure.persistence.repositories.document_repo_impl import (
    DocumentRepositoryImpl,
)
from medimind_agent.application.services.document_service import DocumentService
from medimind_agent.infrastructure.tasks.document_tasks import (
    process_pending_documents_task,
    process_document_task,
    delete_document_nodes_task,
)

router = APIRouter(prefix="/admin", tags=["Admin"])


class ReprocessResponse(BaseModel):
    queued_count: int
    document_ids: list[str]


class ReindexResponse(BaseModel):
    document_id: str
    status: str
    message: str


class IndexStats(BaseModel):
    documents: Dict[str, int]
    documents_by_status: Dict[str, int]


@router.post("/reprocess-pending", response_model=ReprocessResponse)
async def reprocess_pending(
    dry_run: bool = False,
    document_repo: DocumentRepositoryImpl = Depends(get_document_repo),
):
    """Queue processing of all uploaded/failed/pending documents."""
    target_statuses = (
        DocumentStatus.UPLOADED.value,
        DocumentStatus.FAILED.value,
        DocumentStatus.PENDING.value,
    )
    pending_count = 0
    for status in (DocumentStatus.UPLOADED, DocumentStatus.FAILED, DocumentStatus.PENDING):
        pending_count += await document_repo.count_all(status=status)
    # Collect ids if not too many
    pending_ids: list[str] = []
    if pending_count <= 200:
        # light-weight fetch
        from medimind_agent.infrastructure.persistence.models import DocumentModel
        from sqlalchemy import select
        result = await document_repo._session.execute(
            select(DocumentModel.id).where(DocumentModel.status.in_(target_statuses))
        )
        pending_ids = [str(row[0]) for row in result.all()]

    if dry_run:
        return ReprocessResponse(queued_count=pending_count, document_ids=pending_ids)

    # Trigger celery task (processes all pending)
    process_pending_documents_task.delay()
    return ReprocessResponse(queued_count=pending_count, document_ids=pending_ids)


@router.post("/documents/{document_id}/reindex", response_model=ReindexResponse)
async def reindex_document(
    document_id: str,
    force: bool = False,
    document_repo: DocumentRepositoryImpl = Depends(get_document_repo),
    document_service: DocumentService = Depends(get_document_service),
):
    """Rebuild a single document's indexes (pgvector + ES)."""
    doc = await document_repo.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not force and doc.status in {DocumentStatus.PENDING, DocumentStatus.PROCESSING}:
        raise HTTPException(status_code=400, detail=f"Document status={doc.status.value}, set force=true to reindex")

    # Reset status to pending so worker can claim it atomically.
    await document_repo.update_status(
        document_id,
        DocumentStatus.PENDING,
        error_message=None,
        processing_stage="queued",
        processing_meta={"queued_by": "admin_reindex", "force": bool(force)},
    )
    await document_repo.commit()

    # Clear old index nodes best-effort
    delete_document_nodes_task.delay(document_id)
    # Re-run full processing (extract + chunk + index)
    process_document_task.delay(document_id)

    return ReindexResponse(document_id=document_id, status="queued", message="Reindex task queued")


@router.get("/index-stats", response_model=IndexStats)
async def index_stats(
    document_repo: DocumentRepositoryImpl = Depends(get_document_repo),
):
    """Return basic document/index stats."""
    total = await document_repo.count_all()
    by_status = {
        status.value: await document_repo.count_all(status=status)
        for status in DocumentStatus
    }
    return IndexStats(documents={"total": total}, documents_by_status=by_status)
