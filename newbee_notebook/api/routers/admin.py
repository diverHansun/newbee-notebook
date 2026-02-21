"""Admin management endpoints for document processing and index monitoring."""

import gc
import os
import platform
from typing import Dict, Iterable, Optional
from urllib.parse import urlsplit, urlunsplit

import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from newbee_notebook.api.dependencies import get_document_repo
from newbee_notebook.core.common.config import get_document_processing_config
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


# ---- System memory diagnostics & cleanup --------------------------------


class SystemCleanupResponse(BaseModel):
    status: str
    gc_collected: int = Field(description="Number of objects collected by gc.collect()")
    rss_before_mb: Optional[float] = Field(default=None, description="RSS before cleanup (MB)")
    rss_after_mb: Optional[float] = Field(default=None, description="RSS after cleanup (MB)")


class SystemMemoryResponse(BaseModel):
    backend: Dict[str, object] = Field(description="Backend process memory stats")
    mineru: Dict[str, object] = Field(description="MinerU service health status")


def _get_rss_mb() -> Optional[float]:
    """Read current process RSS in MB from /proc or psutil."""
    try:
        # Linux
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024, 1)
    except Exception:
        pass
    try:
        # Windows / fallback
        import psutil
        proc = psutil.Process(os.getpid())
        return round(proc.memory_info().rss / (1024 ** 2), 1)
    except Exception:
        return None


def _get_mineru_api_url() -> str:
    """Resolve the MinerU local API base URL from config."""
    try:
        cfg = get_document_processing_config()
        dp_cfg = cfg.get("document_processing", cfg)
        local_cfg = dp_cfg.get("mineru_local", {}) or {}
        return str(local_cfg.get("api_url", "http://mineru-api:8000")).rstrip("/")
    except Exception:
        return "http://mineru-api:8000"


def _get_mineru_probe_urls() -> list[str]:
    """Build candidate MinerU URLs for mixed host/docker deployments."""
    primary = _get_mineru_api_url().rstrip("/")
    candidates = [primary]

    try:
        parsed = urlsplit(primary)
    except Exception:
        return candidates

    public = os.getenv("MINERU_LOCAL_API_PUBLIC_URL", "").strip().rstrip("/")
    if public:
        candidates.append(public)

    if parsed.hostname == "mineru-api":
        scheme = parsed.scheme or "http"
        port = parsed.port or 8000
        host_port = 8001 if port == 8000 else port
        host_candidate = urlunsplit((scheme, f"localhost:{host_port}", "", "", ""))
        candidates.append(host_candidate.rstrip("/"))

    # Deduplicate while preserving order
    deduped: list[str] = []
    for url in candidates:
        if url and url not in deduped:
            deduped.append(url)
    return deduped


@router.post("/system/cleanup", response_model=SystemCleanupResponse)
async def system_cleanup():
    """Force Python garbage collection on the backend process.

    Useful after processing large batches of documents to reclaim memory
    held by accumulated temporary objects (ZIP data, markdown content,
    image bytes, etc.).
    """
    rss_before = _get_rss_mb()
    collected = gc.collect()
    rss_after = _get_rss_mb()

    return SystemCleanupResponse(
        status="ok",
        gc_collected=collected,
        rss_before_mb=rss_before,
        rss_after_mb=rss_after,
    )


@router.get("/system/memory", response_model=SystemMemoryResponse)
async def system_memory():
    """Report backend process memory and MinerU service health.

    Backend memory is read directly; MinerU health is probed via its
    /docs endpoint (same endpoint used by Docker healthcheck).
    """
    # Backend process stats
    backend: Dict[str, object] = {
        "pid": os.getpid(),
        "platform": platform.system(),
    }
    rss = _get_rss_mb()
    if rss is not None:
        backend["rss_mb"] = rss
    try:
        # Linux: also read VmSize
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmSize:"):
                    backend["vms_mb"] = round(int(line.split()[1]) / 1024, 1)
    except Exception:
        pass

    # MinerU health probe (best-effort)
    probe_urls = _get_mineru_probe_urls()
    mineru: Dict[str, object] = {"api_url": probe_urls[0], "probe_candidates": probe_urls}
    for idx, mineru_url in enumerate(probe_urls):
        try:
            resp = http_requests.get(f"{mineru_url}/docs", timeout=3.0)
            if resp.ok:
                mineru["status"] = "healthy"
            else:
                mineru["status"] = f"unhealthy ({resp.status_code})"
            mineru["probe_url"] = mineru_url
            if idx > 0:
                mineru["note"] = "primary mineru url unreachable; used fallback probe url"
            break
        except http_requests.ConnectionError:
            continue
        except Exception as exc:
            mineru["status"] = f"error: {exc}"
            mineru["probe_url"] = mineru_url
            break
    else:
        mineru["status"] = "unreachable"

    return SystemMemoryResponse(backend=backend, mineru=mineru)
