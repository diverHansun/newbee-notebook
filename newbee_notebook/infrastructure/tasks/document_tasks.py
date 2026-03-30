"""Celery tasks for document processing pipelines."""

import asyncio
import gc
import inspect
import logging
import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Awaitable, Callable, Iterable
from uuid import uuid4

from llama_index.core.vector_stores import FilterOperator, MetadataFilter, MetadataFilters
from llama_index.readers.file import MarkdownReader

from newbee_notebook.core.common.config import (
    get_documents_directory,
    get_pgvector_config_for_provider,
    get_storage_config,
)
from newbee_notebook.core.common.config_db import (
    sync_embedding_runtime_env_from_db,
    sync_mineru_runtime_env_from_db,
)
from newbee_notebook.core.engine.index_builder import load_es_index, load_pgvector_index
from newbee_notebook.core.rag.embeddings import build_embedding
from newbee_notebook.core.rag.text_splitter.splitter import split_documents
from newbee_notebook.domain.entities.document import Document
from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.domain.value_objects.processing_stage import ProcessingStage
from newbee_notebook.infrastructure.document_processing import DocumentProcessor
from newbee_notebook.infrastructure.elasticsearch import ElasticsearchConfig
from newbee_notebook.infrastructure.persistence.database import get_database
from newbee_notebook.infrastructure.persistence.repositories.document_repo_impl import (
    DocumentRepositoryImpl,
)
from newbee_notebook.infrastructure.pgvector import PGVectorConfig
from newbee_notebook.infrastructure.storage import get_runtime_storage_backend
from newbee_notebook.infrastructure.storage.base import StorageBackend
from newbee_notebook.infrastructure.storage.object_keys import build_storage_key_candidates
from newbee_notebook.infrastructure.tasks.celery_app import app
from newbee_notebook.infrastructure.tasks.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)
_EMBED_MODEL = None
_EMBED_MODEL_SIGNATURE = None
_PIPELINE_LOCK_REDIS = None
_PIPELINE_LOCK_DISABLED = False
_PIPELINE_LOCK_RELEASE_SCRIPT = (
    "if redis.call('GET', KEYS[1]) == ARGV[1] then "
    "return redis.call('DEL', KEYS[1]) "
    "else return 0 end"
)


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _cleanup_worker_memory(task_name: str, document_id: str | None = None) -> None:
    """Best-effort memory cleanup after each heavy document task."""
    collected = gc.collect()
    cuda_cleaned = False

    if _truthy(os.getenv("WORKER_CUDA_EMPTY_CACHE", "true"), default=True):
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                cuda_cleaned = True
        except Exception:
            cuda_cleaned = False

    logger.info(
        "[%s] worker cleanup done document_id=%s gc_collected=%d cuda_cache_cleared=%s",
        task_name,
        document_id or "-",
        collected,
        cuda_cleaned,
    )


def _get_pipeline_lock_ttl_seconds() -> int:
    """Get lock ttl from env with a conservative default."""
    raw_ttl = os.getenv("DOCUMENT_PIPELINE_LOCK_TTL_SECONDS", "1800")
    try:
        ttl = int(raw_ttl)
    except ValueError:
        ttl = 1800
    return max(30, ttl)


def _get_pipeline_lock_redis_url() -> str | None:
    """Resolve redis URL for distributed document lock."""
    if os.getenv("PIPELINE_LOCK_REDIS_URL"):
        return os.getenv("PIPELINE_LOCK_REDIS_URL")
    if os.getenv("REDIS_URL"):
        return os.getenv("REDIS_URL")
    broker = os.getenv("CELERY_BROKER_URL", "")
    if broker.startswith("redis://") or broker.startswith("rediss://"):
        return broker
    return None


def _get_pipeline_lock_key(document_id: str) -> str:
    """Build deterministic lock key by document id."""
    return f"newbee:notebook:document_pipeline:{document_id}"


def _get_pipeline_lock_client():
    """Create/cache redis client for distributed lock.

    Use sync redis client to avoid event-loop affinity issues under
    Celery prefork workers + asyncio.run per task invocation.
    """
    global _PIPELINE_LOCK_REDIS, _PIPELINE_LOCK_DISABLED

    if _PIPELINE_LOCK_DISABLED:
        return None
    if _PIPELINE_LOCK_REDIS is not None:
        return _PIPELINE_LOCK_REDIS

    redis_url = _get_pipeline_lock_redis_url()
    if not redis_url:
        _PIPELINE_LOCK_DISABLED = True
        logger.warning("Pipeline lock disabled: redis url is not configured")
        return None

    try:
        import redis
    except Exception as exc:  # noqa: BLE001
        _PIPELINE_LOCK_DISABLED = True
        logger.warning("Pipeline lock disabled: redis client unavailable (%s)", exc)
        return None

    try:
        _PIPELINE_LOCK_REDIS = redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    except Exception as exc:  # noqa: BLE001
        _PIPELINE_LOCK_DISABLED = True
        logger.warning("Pipeline lock disabled: redis client init failed (%s)", exc)
        return None

    return _PIPELINE_LOCK_REDIS


async def _acquire_pipeline_lock(document_id: str, mode: str) -> tuple[str | None, str | None, bool]:
    """Acquire per-document distributed lock."""
    client = _get_pipeline_lock_client()
    if client is None:
        return None, None, True

    lock_key = _get_pipeline_lock_key(document_id)
    lock_token = uuid4().hex
    try:
        acquired = await asyncio.to_thread(
            client.set,
            name=lock_key,
            value=lock_token,
            nx=True,
            ex=_get_pipeline_lock_ttl_seconds(),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[%s] Pipeline lock unavailable for %s, continuing without lock: %s",
            mode,
            document_id,
            exc,
        )
        return None, None, True

    if acquired:
        return lock_key, lock_token, True

    logger.info("[%s] Document %s lock is already held, skip duplicate task", mode, document_id)
    return lock_key, None, False


async def _release_pipeline_lock(lock_key: str | None, lock_token: str | None) -> None:
    """Release per-document lock only when token matches."""
    if not lock_key or not lock_token:
        return

    client = _get_pipeline_lock_client()
    if client is None:
        return

    try:
        await asyncio.to_thread(client.eval, _PIPELINE_LOCK_RELEASE_SCRIPT, 1, lock_key, lock_token)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to release pipeline lock key=%s: %s", lock_key, exc)


@app.task(name="newbee_notebook.infrastructure.tasks.document_tasks.process_document_task")
def process_document_task(document_id: str, force: bool = False) -> None:
    """Run full pipeline (convert + index), with optional forced cleanup."""
    try:
        asyncio.run(_process_document_async(document_id, force=force))
    finally:
        _cleanup_worker_memory(task_name="process_document_task", document_id=document_id)


@app.task(name="newbee_notebook.infrastructure.tasks.document_tasks.convert_document_task")
def convert_document_task(document_id: str, force: bool = False) -> None:
    """Run conversion-only pipeline."""
    try:
        asyncio.run(_convert_document_async(document_id, force=force))
    finally:
        _cleanup_worker_memory(task_name="convert_document_task", document_id=document_id)


@app.task(name="newbee_notebook.infrastructure.tasks.document_tasks.index_document_task")
def index_document_task(document_id: str, force: bool = False) -> None:
    """Run indexing-only pipeline."""
    try:
        asyncio.run(_index_document_async(document_id, force=force))
    finally:
        _cleanup_worker_memory(task_name="index_document_task", document_id=document_id)


@app.task(name="newbee_notebook.infrastructure.tasks.document_tasks.convert_pending_task")
def convert_pending_task(document_ids: list[str] | None = None) -> dict:
    """Dispatch conversion tasks for uploaded/failed docs."""
    return asyncio.run(_convert_pending_async(document_ids=document_ids))


@app.task(name="newbee_notebook.infrastructure.tasks.document_tasks.index_pending_task")
def index_pending_task(document_ids: list[str] | None = None) -> dict:
    """Dispatch indexing tasks for converted docs."""
    return asyncio.run(_index_pending_async(document_ids=document_ids))


@app.task(name="newbee_notebook.infrastructure.tasks.document_tasks.process_pending_documents_task")
def process_pending_documents_task(document_ids: list[str] | None = None) -> dict:
    """Backward-compatible full-pipeline dispatcher for pending docs."""
    return asyncio.run(_process_pending_async(document_ids=document_ids))


@app.task(name="newbee_notebook.infrastructure.tasks.document_tasks.delete_document_nodes_task")
def delete_document_nodes_task(document_id: str) -> None:
    asyncio.run(_delete_document_nodes_async(document_id))


async def _execute_pipeline(
    document_id: str,
    mode: str,
    from_statuses: list[DocumentStatus],
    initial_stage: ProcessingStage,
    pipeline_fn: Callable[[PipelineContext], Awaitable[None]],
    skip_if_status: set[DocumentStatus] | None = None,
) -> None:
    """Unified execution framework for document pipelines."""
    lock_key, lock_token, should_run = await _acquire_pipeline_lock(document_id=document_id, mode=mode)
    if not should_run:
        return

    try:
        db = await get_database()
        async with db.session() as session:
            doc_repo = DocumentRepositoryImpl(session)

            document = await doc_repo.get(document_id)
            if not document:
                logger.error("[%s] Document %s not found", mode, document_id)
                return

            if skip_if_status and document.status in skip_if_status:
                logger.info(
                    "[%s] Document %s status=%s, skip",
                    mode,
                    document_id,
                    document.status.value,
                )
                return
            if document.status == DocumentStatus.PROCESSING:
                logger.info("[%s] Document %s already processing, skip", mode, document_id)
                return

            original_status = document.status
            claimed = await doc_repo.claim_processing(
                document_id=document_id,
                from_statuses=from_statuses,
                processing_stage=initial_stage.value,
                processing_meta={"mode": mode},
            )
            if not claimed:
                latest = await doc_repo.get(document_id)
                latest_status = latest.status.value if latest else "unknown"
                logger.warning(
                    "[%s] Failed to claim document %s (current=%s)",
                    mode,
                    document_id,
                    latest_status,
                )
                return
            await session.commit()

            document = await doc_repo.get(document_id)
            if not document:
                logger.error("[%s] Document %s disappeared after claim", mode, document_id)
                return

            ctx = PipelineContext(
                document_id=document_id,
                document=document,
                doc_repo=doc_repo,
                session=session,
                mode=mode,
                original_status=original_status,
            )
            ctx._current_stage = initial_stage.value

            try:
                await pipeline_fn(ctx)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "[%s] Pipeline failed for %s at stage=%s: %s",
                    mode,
                    document_id,
                    ctx.current_stage,
                    exc,
                    exc_info=True,
                )

                # Ensure any uncommitted writes from pipeline_fn are not persisted.
                await session.rollback()

                if ctx.indexed_anything:
                    try:
                        await _delete_document_nodes_async(document_id)
                    except Exception:  # noqa: BLE001
                        logger.warning("Compensation cleanup failed for %s", document_id)

                latest = await doc_repo.get(document_id)
                has_conversion = bool((latest or document).content_path)
                if not has_conversion and ctx.current_stage in {
                    ProcessingStage.SPLITTING.value,
                    ProcessingStage.INDEXING_PG.value,
                    ProcessingStage.INDEXING_ES.value,
                    ProcessingStage.FINALIZING.value,
                }:
                    has_conversion = True

                await doc_repo.update_status(
                    document_id=document_id,
                    status=DocumentStatus.FAILED,
                    error_message=str(exc)[:500],
                    processing_stage=ctx.current_stage,
                    processing_meta={
                        "failed_stage": ctx.current_stage,
                        "conversion_preserved": bool(has_conversion),
                        "mode": mode,
                    },
                )
                await session.commit()
                # Keep database state and task state consistent for monitoring/retry.
                raise
    finally:
        await _release_pipeline_lock(lock_key=lock_key, lock_token=lock_token)


async def _convert_document_async(document_id: str, force: bool = False) -> None:
    async def _do_convert(ctx: PipelineContext) -> None:
        if force:
            try:
                await _delete_document_nodes_async(ctx.document_id)
            except Exception as cleanup_exc:  # noqa: BLE001
                logger.warning(
                    "Pre-conversion cleanup failed for %s: %s",
                    ctx.document_id,
                    cleanup_exc,
                )

        await ctx.set_stage(ProcessingStage.CONVERTING)
        await sync_mineru_runtime_env_from_db(ctx.session)
        processor = DocumentProcessor()
        async with _materialize_document_source(ctx.document) as source_path:
            result, rel_content_path, content_size = await processor.process_and_save(
                document_id=ctx.document_id,
                file_path=str(source_path),
            )

        await ctx.set_stage(ProcessingStage.FINALIZING)
        await ctx.set_terminal_status(
            status=DocumentStatus.CONVERTED,
            chunk_count=0,
            page_count=result.page_count or 0,
            content_path=rel_content_path,
            content_size=content_size,
            content_format="markdown",
        )

    from_statuses = [
        DocumentStatus.UPLOADED,
        DocumentStatus.PENDING,
        DocumentStatus.FAILED,
    ]
    if force:
        from_statuses.extend([DocumentStatus.COMPLETED, DocumentStatus.CONVERTED])

    await _execute_pipeline(
        document_id=document_id,
        mode="convert_only",
        from_statuses=from_statuses,
        initial_stage=ProcessingStage.QUEUED,
        pipeline_fn=_do_convert,
        skip_if_status=None if force else {DocumentStatus.CONVERTED, DocumentStatus.COMPLETED},
    )


async def _index_document_async(document_id: str, force: bool = False) -> None:
    async def _do_index(ctx: PipelineContext) -> None:
        if force:
            try:
                await _delete_document_nodes_async(ctx.document_id)
            except Exception as cleanup_exc:  # noqa: BLE001
                logger.warning(
                    "Pre-index cleanup failed for %s: %s",
                    ctx.document_id,
                    cleanup_exc,
                )

        content_path = ctx.document.content_path
        if not content_path:
            raise RuntimeError(f"Document {ctx.document_id} has no content_path, cannot index")

        await ctx.set_stage(ProcessingStage.SPLITTING)
        nodes = await _load_markdown_nodes(ctx.document, content_path)

        await _index_to_stores(nodes, ctx)

        await ctx.set_stage(ProcessingStage.FINALIZING, {"chunk_count": len(nodes)})
        await ctx.set_terminal_status(
            status=DocumentStatus.COMPLETED,
            chunk_count=len(nodes),
        )

    from_statuses = [DocumentStatus.CONVERTED]
    if force:
        from_statuses.extend([DocumentStatus.COMPLETED, DocumentStatus.FAILED])

    await _execute_pipeline(
        document_id=document_id,
        mode="index_only",
        from_statuses=from_statuses,
        initial_stage=ProcessingStage.QUEUED,
        pipeline_fn=_do_index,
        skip_if_status=None if force else {DocumentStatus.COMPLETED},
    )


async def _process_document_async(document_id: str, force: bool = False) -> None:
    """Full pipeline with smart conversion skipping for converted docs."""

    async def _do_full_pipeline(ctx: PipelineContext) -> None:
        if force:
            try:
                await _delete_document_nodes_async(ctx.document_id)
            except Exception as cleanup_exc:  # noqa: BLE001
                logger.warning(
                    "Pre-full-pipeline cleanup failed for %s: %s",
                    ctx.document_id,
                    cleanup_exc,
                )

        skip_conversion = ctx.original_status == DocumentStatus.CONVERTED

        if not skip_conversion:
            await ctx.set_stage(ProcessingStage.CONVERTING)
            await sync_mineru_runtime_env_from_db(ctx.session)
            processor = DocumentProcessor()
            async with _materialize_document_source(ctx.document) as source_path:
                result, rel_content_path, content_size = await processor.process_and_save(
                    document_id=ctx.document_id,
                    file_path=str(source_path),
                )

            # Persist conversion artifacts for subsequent stages and retries.
            await ctx.doc_repo.update_status(
                document_id=ctx.document_id,
                status=DocumentStatus.PROCESSING,
                page_count=result.page_count or 0,
                content_path=rel_content_path,
                content_size=content_size,
                content_format="markdown",
                error_message=None,
            )
            await ctx.session.commit()
            content_path = rel_content_path
        else:
            content_path = ctx.document.content_path
            if not content_path:
                raise RuntimeError(
                    f"Document {ctx.document_id} status=converted but content_path is missing"
                )
            logger.info(
                "Document %s already converted, skipping conversion",
                ctx.document_id,
            )

        await ctx.set_stage(ProcessingStage.SPLITTING)
        nodes = await _load_markdown_nodes(ctx.document, content_path)

        await _index_to_stores(nodes, ctx)

        await ctx.set_stage(ProcessingStage.FINALIZING, {"chunk_count": len(nodes)})
        await ctx.set_terminal_status(
            status=DocumentStatus.COMPLETED,
            chunk_count=len(nodes),
        )

    from_statuses = [
        DocumentStatus.UPLOADED,
        DocumentStatus.PENDING,
        DocumentStatus.FAILED,
        DocumentStatus.CONVERTED,
    ]
    if force:
        from_statuses.append(DocumentStatus.COMPLETED)

    await _execute_pipeline(
        document_id=document_id,
        mode="full_pipeline",
        from_statuses=from_statuses,
        initial_stage=ProcessingStage.QUEUED,
        pipeline_fn=_do_full_pipeline,
        skip_if_status=None if force else {DocumentStatus.COMPLETED},
    )


async def _resolve_existing_storage_key(
    storage: StorageBackend,
    candidates: list[str],
) -> str:
    for candidate in candidates:
        if await storage.exists(candidate):
            return candidate
    raise FileNotFoundError(f"Object not found in storage. candidates={candidates}")


def _build_storage_candidates(raw_path: str | None, default_key: str | None) -> list[str]:
    return build_storage_key_candidates(
        raw_path=raw_path,
        default_key=default_key,
        documents_root=get_documents_directory(),
    )


async def _resolve_source_storage_key(document: Document, storage: StorageBackend) -> str:
    candidates = _build_storage_candidates(
        raw_path=document.file_path,
        default_key=f"{document.document_id}/original/{Path(document.file_path).name}",
    )
    return await _resolve_existing_storage_key(storage, candidates)


async def _resolve_content_storage_key(
    document: Document,
    content_path: str,
    storage: StorageBackend,
) -> str:
    candidates = _build_storage_candidates(
        raw_path=content_path,
        default_key=f"{document.document_id}/markdown/content.md",
    )
    return await _resolve_existing_storage_key(storage, candidates)


@asynccontextmanager
async def _materialize_storage_object(
    storage: StorageBackend,
    object_key: str,
) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="newbee-storage-"))
    local_path = temp_dir / Path(object_key).name
    try:
        await storage.download_to_path(object_key, str(local_path))
        yield local_path
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@asynccontextmanager
async def _materialize_document_source(document: Document) -> Path:
    storage = get_runtime_storage_backend()
    object_key = await _resolve_source_storage_key(document, storage)
    async with _materialize_storage_object(storage, object_key) as local_path:
        yield local_path


@asynccontextmanager
async def _materialize_document_content(document: Document, content_path: str) -> Path:
    storage = get_runtime_storage_backend()
    object_key = await _resolve_content_storage_key(document, content_path, storage)
    async with _materialize_storage_object(storage, object_key) as local_path:
        yield local_path


async def _load_markdown_nodes(
    document: Document,
    content_path: str,
    *,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
):
    """Load markdown file and split into nodes with metadata."""
    async with _materialize_document_content(document, content_path) as content_abs_path:
        reader = MarkdownReader(remove_hyperlinks=False, remove_images=False)
        docs = reader.load_data(
            file=str(content_abs_path),
            extra_info={
                "source_document_id": document.document_id,
                "ref_doc_id": document.document_id,
                "doc_id": document.document_id,
                "document_id": document.document_id,
                "library_id": document.library_id,
                "notebook_id": document.notebook_id,
                "title": document.title,
            },
        )

    nodes = split_documents(docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    for idx, node in enumerate(nodes):
        meta = getattr(node, "metadata", {}) or {}
        meta["chunk_index"] = idx
        meta["chunk_id"] = getattr(node, "node_id", "")
        meta["source_document_id"] = document.document_id
        meta["ref_doc_id"] = document.document_id
        meta["doc_id"] = document.document_id
        meta["document_id"] = document.document_id
        node.metadata = meta
        try:
            node.ref_doc_id = document.document_id
            node.doc_id = document.document_id
        except Exception:
            pass
    return nodes


async def _index_to_stores(nodes, ctx: PipelineContext) -> None:
    """Write nodes into pgvector and Elasticsearch with stage tracking."""
    chunk_count = len(nodes)

    await ctx.set_stage(ProcessingStage.INDEXING_PG, {"chunk_count": chunk_count})
    await _index_pg_nodes(nodes, session=ctx.session)
    ctx.indexed_anything = True

    await ctx.set_stage(ProcessingStage.INDEXING_ES, {"chunk_count": chunk_count})
    await _index_es_nodes(nodes, session=ctx.session)


async def _find_documents_by_status(
    doc_repo: DocumentRepositoryImpl,
    statuses: Iterable[DocumentStatus],
    document_ids: list[str] | None = None,
    page_size: int = 200,
) -> list[Document]:
    """Find library documents by status with optional ID filtering."""
    all_docs: list[Document] = []
    for status in statuses:
        offset = 0
        while True:
            docs = await doc_repo.list_by_library(limit=page_size, offset=offset, status=status)
            if not docs:
                break
            all_docs.extend(docs)
            if len(docs) < page_size:
                break
            offset += page_size

    if document_ids is not None:
        wanted = set(document_ids)
        all_docs = [doc for doc in all_docs if doc.document_id in wanted]

    deduped: list[Document] = []
    seen: set[str] = set()
    for doc in all_docs:
        if doc.document_id in seen:
            continue
        seen.add(doc.document_id)
        deduped.append(doc)
    return deduped


async def _convert_pending_async(document_ids: list[str] | None = None) -> dict:
    """Dispatch conversion tasks for uploaded/failed docs."""
    db = await get_database()
    async with db.session() as session:
        doc_repo = DocumentRepositoryImpl(session)
        docs = await _find_documents_by_status(
            doc_repo=doc_repo,
            statuses=[DocumentStatus.UPLOADED, DocumentStatus.FAILED],
            document_ids=document_ids,
        )

    dispatched: list[str] = []
    for doc in docs:
        convert_document_task.delay(doc.document_id)
        dispatched.append(doc.document_id)

    return {
        "queued_count": len(dispatched),
        "document_ids": dispatched,
    }


async def _index_pending_async(document_ids: list[str] | None = None) -> dict:
    """Dispatch indexing tasks for converted docs."""
    db = await get_database()
    async with db.session() as session:
        doc_repo = DocumentRepositoryImpl(session)
        docs = await _find_documents_by_status(
            doc_repo=doc_repo,
            statuses=[DocumentStatus.CONVERTED],
            document_ids=document_ids,
        )

    dispatched: list[str] = []
    for doc in docs:
        index_document_task.delay(doc.document_id)
        dispatched.append(doc.document_id)

    return {
        "queued_count": len(dispatched),
        "document_ids": dispatched,
    }


async def _process_pending_async(document_ids: list[str] | None = None) -> dict:
    """Dispatch full pipeline tasks for uploaded/failed/pending docs."""
    db = await get_database()
    async with db.session() as session:
        doc_repo = DocumentRepositoryImpl(session)
        docs = await _find_documents_by_status(
            doc_repo=doc_repo,
            statuses=[
                DocumentStatus.UPLOADED,
                DocumentStatus.FAILED,
                DocumentStatus.PENDING,
            ],
            document_ids=document_ids,
        )

    dispatched: list[str] = []
    for doc in docs:
        process_document_task.delay(doc.document_id)
        dispatched.append(doc.document_id)

    return {
        "queued_count": len(dispatched),
        "document_ids": dispatched,
    }


async def _get_embed_model(session=None):
    global _EMBED_MODEL, _EMBED_MODEL_SIGNATURE

    owns_session = session is None
    if owns_session:
        db = await get_database()
        session_ctx = db.session()
        session = await session_ctx.__aenter__()
    else:
        session_ctx = None

    try:
        embedding_cfg = await sync_embedding_runtime_env_from_db(session)
    finally:
        if session_ctx is not None:
            await session_ctx.__aexit__(None, None, None)

    signature = (
        embedding_cfg.get("provider"),
        embedding_cfg.get("mode"),
        embedding_cfg.get("api_model"),
        embedding_cfg.get("model"),
        embedding_cfg.get("model_path"),
    )
    if _EMBED_MODEL is None or _EMBED_MODEL_SIGNATURE != signature:
        _EMBED_MODEL = build_embedding()
        _EMBED_MODEL_SIGNATURE = signature
    return _EMBED_MODEL, embedding_cfg


async def _index_pg_nodes(nodes, *, session=None):
    """Index nodes into pgvector."""
    embed_model, embedding_cfg = await _get_embed_model(session=session)
    storage_cfg = get_storage_config()

    pg_cfg = storage_cfg.get("postgresql", {})
    provider = str(embedding_cfg["provider"])
    pgvector_provider_cfg = get_pgvector_config_for_provider(provider)
    pg_config = PGVectorConfig(
        host=pg_cfg.get("host", "localhost"),
        port=pg_cfg.get("port", 5432),
        database=pg_cfg.get("database", "newbee_notebook"),
        user=pg_cfg.get("user", "postgres"),
        password=pg_cfg.get("password", ""),
        table_name=pgvector_provider_cfg["table_name"],
        embedding_dimension=pgvector_provider_cfg["embedding_dimension"],
    )
    pg_index = await load_pgvector_index(embed_model, pg_config)
    try:
        pg_index.insert_nodes(nodes)
    finally:
        await _close_vector_index(pg_index)


async def _index_es_nodes(nodes, *, session=None):
    """Index nodes into Elasticsearch."""
    embed_model, _embedding_cfg = await _get_embed_model(session=session)
    storage_cfg = get_storage_config()

    es_cfg = storage_cfg.get("elasticsearch", {})
    es_config = ElasticsearchConfig(
        url=es_cfg.get("url", "http://localhost:9200"),
        index_name=es_cfg.get("index_name", "newbee_notebook_docs"),
        api_key=es_cfg.get("api_key", None),
        cloud_id=es_cfg.get("cloud_id", None),
    )
    es_index = await load_es_index(embed_model, es_config)
    try:
        es_index.insert_nodes(nodes)
    finally:
        await _close_vector_index(es_index)


async def _close_closeable(resource) -> bool:
    """Best-effort close for resources exposing sync or async close()."""
    if resource is None:
        return False

    close = getattr(resource, "close", None)
    if not callable(close):
        return False

    try:
        result = close()
        if inspect.isawaitable(result):
            await result
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to close resource %s: %s", type(resource).__name__, exc)
        return False


async def _close_vector_index(index) -> None:
    """Close resources held by a VectorStoreIndex without leaking clients."""
    vector_store = getattr(index, "vector_store", None)
    nested_store = getattr(vector_store, "_store", None) if vector_store is not None else None

    closed = await _close_closeable(nested_store)
    if not closed:
        await _close_closeable(vector_store)


async def _delete_document_nodes_async(document_id: str):
    """Delete vector/ES nodes belonging to a document (best effort)."""
    try:
        db = await get_database()
        async with db.session() as session:
            embed_model, embedding_cfg = await _get_embed_model(session=session)
        storage_cfg = get_storage_config()

        pg_cfg = storage_cfg.get("postgresql", {})
        provider = str(embedding_cfg["provider"])
        pgvector_provider_cfg = get_pgvector_config_for_provider(provider)
        pg_config = PGVectorConfig(
            host=pg_cfg.get("host", "localhost"),
            port=pg_cfg.get("port", 5432),
            database=pg_cfg.get("database", "newbee_notebook"),
            user=pg_cfg.get("user", "postgres"),
            password=pg_cfg.get("password", ""),
            table_name=pgvector_provider_cfg["table_name"],
            embedding_dimension=pgvector_provider_cfg["embedding_dimension"],
        )
        try:
            pg_index = await load_pgvector_index(embed_model, pg_config)
            try:
                filters = MetadataFilters(
                    filters=[
                        MetadataFilter(
                            key="source_document_id",
                            value=document_id,
                            operator=FilterOperator.EQ,
                        )
                    ]
                )
                pg_index.vector_store.delete_nodes(filters=filters)
            finally:
                await _close_vector_index(pg_index)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Delete pgvector nodes failed for %s: %s", document_id, exc)

        es_cfg = storage_cfg.get("elasticsearch", {})
        es_config = ElasticsearchConfig(
            url=es_cfg.get("url", "http://localhost:9200"),
            index_name=es_cfg.get("index_name", "newbee_notebook_docs"),
            api_key=es_cfg.get("api_key", None),
            cloud_id=es_cfg.get("cloud_id", None),
        )
        try:
            es_index = await load_es_index(embed_model, es_config)
            try:
                filters = MetadataFilters(
                    filters=[
                        MetadataFilter(
                            key="source_document_id",
                            value=document_id,
                            operator=FilterOperator.EQ,
                        )
                    ]
                )
                es_index.vector_store.delete_nodes(filters=filters)
            finally:
                await _close_vector_index(es_index)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Delete ES nodes failed for %s: %s", document_id, exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("delete_document_nodes_task failed for %s: %s", document_id, exc)
