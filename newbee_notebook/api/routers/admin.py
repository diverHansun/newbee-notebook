"""Admin management endpoints for document processing and index monitoring."""

from typing import Dict, Iterable, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from newbee_notebook.api.dependencies import get_document_repo
from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.infrastructure.persistence.repositories.document_repo_impl import (
    DocumentRepositoryImpl,
)
from newbee_notebook.infrastructure.tasks.document_tasks import (
    convert_document_task,
    convert_pending_task,
    index_document_task,
    index_pending_task,
    process_document_task,
    process_pending_documents_task,
)

router = APIRouter(prefix="/admin", tags=["Admin"])


class ReprocessResponse(BaseModel):
    queued_count: int
    document_ids: list[str]


class TaskDispatchResponse(BaseModel):
    document_id: str
    status: str
    message: str
    action: str


class ReindexResponse(BaseModel):
    document_id: str
    status: str
    message: str
    action: str


class BatchDispatchRequest(BaseModel):
    document_ids: Optional[list[str]] = Field(default=None)
    dry_run: bool = False


class IndexStats(BaseModel):
    documents: Dict[str, int]
    documents_by_status: Dict[str, int]


async def _collect_doc_ids_by_status(
    document_repo: DocumentRepositoryImpl,
    statuses: Iterable[DocumentStatus],
    document_ids: list[str] | None = None,
    page_size: int = 200,
) -> list[str]:
    ids: list[str] = []
    for status in statuses:
        offset = 0
        while True:
            docs = await document_repo.list_by_library(limit=page_size, offset=offset, status=status)
            if not docs:
                break
            ids.extend([doc.document_id for doc in docs])
            if len(docs) < page_size:
                break
            offset += page_size

    if document_ids is not None:
        wanted = set(document_ids)
        ids = [doc_id for doc_id in ids if doc_id in wanted]

    deduped = list(dict.fromkeys(ids))
    return deduped


@router.post("/reprocess-pending", response_model=ReprocessResponse)
async def reprocess_pending(
    dry_run: bool = False,
    document_repo: DocumentRepositoryImpl = Depends(get_document_repo),
):
    """Queue full pipeline for uploaded/failed/pending documents."""
    pending_ids = await _collect_doc_ids_by_status(
        document_repo=document_repo,
        statuses=[
            DocumentStatus.UPLOADED,
            DocumentStatus.FAILED,
            DocumentStatus.PENDING,
        ],
    )

    if dry_run:
        return ReprocessResponse(queued_count=len(pending_ids), document_ids=pending_ids)

    process_pending_documents_task.delay(pending_ids if pending_ids else None)
    return ReprocessResponse(queued_count=len(pending_ids), document_ids=pending_ids)


@router.post("/documents/{document_id}/convert", response_model=TaskDispatchResponse)
async def convert_document(
    document_id: str,
    force: bool = False,
    document_repo: DocumentRepositoryImpl = Depends(get_document_repo),
):
    """Queue conversion-only task for a single document."""
    doc = await document_repo.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status in {DocumentStatus.PENDING, DocumentStatus.PROCESSING}:
        raise HTTPException(status_code=409, detail=f"Document is {doc.status.value}")

    if not force and doc.status in {DocumentStatus.CONVERTED, DocumentStatus.COMPLETED}:
        return TaskDispatchResponse(
            document_id=document_id,
            status=doc.status.value,
            message="Already converted/completed",
            action="none",
        )

    convert_document_task.delay(document_id, force=force)
    return TaskDispatchResponse(
        document_id=document_id,
        status="queued",
        message="Convert task queued",
        action="convert_only",
    )


@router.post("/documents/{document_id}/index", response_model=TaskDispatchResponse)
async def index_document(
    document_id: str,
    force: bool = False,
    document_repo: DocumentRepositoryImpl = Depends(get_document_repo),
):
    """Queue indexing-only task for a single document."""
    doc = await document_repo.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status == DocumentStatus.PROCESSING:
        raise HTTPException(status_code=409, detail="Document is processing")

    if doc.status in {DocumentStatus.UPLOADED, DocumentStatus.PENDING}:
        raise HTTPException(status_code=400, detail="Document must be converted before indexing")

    if doc.status == DocumentStatus.FAILED and not doc.content_path:
        raise HTTPException(status_code=400, detail="Document has no conversion output; convert first")

    if not force and doc.status == DocumentStatus.COMPLETED:
        return TaskDispatchResponse(
            document_id=document_id,
            status=doc.status.value,
            message="Already completed",
            action="none",
        )

    should_force = force or doc.status == DocumentStatus.COMPLETED or doc.status == DocumentStatus.FAILED

    index_document_task.delay(document_id, force=should_force)
    return TaskDispatchResponse(
        document_id=document_id,
        status="queued",
        message="Index task queued",
        action="index_only",
    )


@router.post("/convert-pending", response_model=ReprocessResponse)
async def convert_pending(
    request: BatchDispatchRequest,
    document_repo: DocumentRepositoryImpl = Depends(get_document_repo),
):
    """Queue conversion-only tasks for uploaded/failed documents."""
    target_ids = await _collect_doc_ids_by_status(
        document_repo=document_repo,
        statuses=[DocumentStatus.UPLOADED, DocumentStatus.FAILED],
        document_ids=request.document_ids,
    )

    if request.dry_run:
        return ReprocessResponse(queued_count=len(target_ids), document_ids=target_ids)

    convert_pending_task.delay(request.document_ids)
    return ReprocessResponse(queued_count=len(target_ids), document_ids=target_ids)


@router.post("/index-pending", response_model=ReprocessResponse)
async def index_pending(
    request: BatchDispatchRequest,
    document_repo: DocumentRepositoryImpl = Depends(get_document_repo),
):
    """Queue indexing-only tasks for converted documents."""
    target_ids = await _collect_doc_ids_by_status(
        document_repo=document_repo,
        statuses=[DocumentStatus.CONVERTED],
        document_ids=request.document_ids,
    )

    if request.dry_run:
        return ReprocessResponse(queued_count=len(target_ids), document_ids=target_ids)

    index_pending_task.delay(request.document_ids)
    return ReprocessResponse(queued_count=len(target_ids), document_ids=target_ids)


@router.post("/documents/{document_id}/reindex", response_model=ReindexResponse)
async def reindex_document(
    document_id: str,
    force: bool = False,
    document_repo: DocumentRepositoryImpl = Depends(get_document_repo),
):
    """Rebuild index with smart routing based on conversion artifacts."""
    doc = await document_repo.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not force and doc.status in {DocumentStatus.PENDING, DocumentStatus.PROCESSING}:
        raise HTTPException(status_code=400, detail=f"Document status={doc.status.value}")

    if not force and doc.content_path:
        index_document_task.delay(document_id, force=True)
        return ReindexResponse(
            document_id=document_id,
            status="queued",
            message="Index-only task queued (conversion preserved)",
            action="index_only",
        )

    process_document_task.delay(document_id, force=force)
    return ReindexResponse(
        document_id=document_id,
        status="queued",
        message="Full reindex task queued",
        action="full_pipeline",
    )


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
