"""
Celery tasks for document processing.
"""

import asyncio
import logging
from pathlib import Path

from medimind_agent.infrastructure.tasks.celery_app import app
from medimind_agent.infrastructure.persistence.database import get_database, close_database
from medimind_agent.infrastructure.persistence.repositories.document_repo_impl import DocumentRepositoryImpl
from medimind_agent.core.rag.text_splitter.splitter import split_documents
from medimind_agent.core.common.config import (
    get_storage_config,
    get_embedding_provider,
    get_pgvector_config_for_provider,
    get_documents_directory,
)
from medimind_agent.core.rag.embeddings import build_embedding
from medimind_agent.core.engine.index_builder import load_pgvector_index, load_es_index
from medimind_agent.domain.value_objects.document_status import DocumentStatus
from medimind_agent.domain.entities.document import Document
from medimind_agent.infrastructure.pgvector import PGVectorConfig
from medimind_agent.infrastructure.elasticsearch import ElasticsearchConfig
from llama_index.readers.file import MarkdownReader
from medimind_agent.infrastructure.document_processing import DocumentProcessor

logger = logging.getLogger(__name__)
_EMBED_MODEL = None
_PROCESSOR = DocumentProcessor()


@app.task(name="medimind_agent.infrastructure.tasks.document_tasks.process_document_task")
def process_document_task(document_id: str):
    asyncio.run(_process_document_async(document_id))


@app.task(name="medimind_agent.infrastructure.tasks.document_tasks.process_pending_documents_task")
def process_pending_documents_task():
    """Process all pending documents (utility for resync)."""
    asyncio.run(_process_all_pending_async())


async def _process_document_async(document_id: str):
    db = await get_database()
    try:
        async with db.session() as session:
            doc_repo = DocumentRepositoryImpl(session)

            document = await doc_repo.get(document_id)
            if not document:
                logger.error("Document %s not found", document_id)
                return

            if document.status == DocumentStatus.COMPLETED:
                logger.info("Document %s already completed, skip processing", document_id)
                return
            if document.status == DocumentStatus.PROCESSING:
                logger.info("Document %s is already processing, skip duplicate run", document_id)
                return

            claimed = await doc_repo.claim_processing(
                document_id,
                processing_stage="converting",
                processing_meta={"stage": "converting"},
            )
            if not claimed:
                current = await doc_repo.get(document_id)
                current_status = current.status.value if current else "unknown"
                logger.info(
                    "Document %s was claimed by another worker or status changed to %s; skip run",
                    document_id,
                    current_status,
                )
                return
            # Commit immediately so API polling can observe PROCESSING state.
            await session.commit()

            current_stage = "converting"
            indexed_anything = False

            async def _set_stage(stage: str, meta: dict | None = None) -> None:
                nonlocal current_stage
                current_stage = stage
                await doc_repo.update_status(
                    document_id=document_id,
                    status=DocumentStatus.PROCESSING,
                    processing_stage=stage,
                    processing_meta=meta,
                )
                await session.commit()

            try:
                source_path = Path(document.file_path)
                if not source_path.is_absolute():
                    source_path = Path(get_documents_directory()) / source_path
                if not source_path.exists():
                    raise FileNotFoundError(f"Original file not found: {source_path}")

                conversion_result, rel_content_path, content_size = await _PROCESSOR.process_and_save(
                    document.document_id, str(source_path)
                )

                await _set_stage("splitting")
                content_abs_path = Path(get_documents_directory()) / rel_content_path
                nodes = _load_markdown_nodes(content_abs_path, document)
                chunk_count = len(nodes)

                await _set_stage("embedding", {"chunk_count": chunk_count})
                await _set_stage("indexing_pg", {"chunk_count": chunk_count})
                await _index_pg_nodes(nodes)
                indexed_anything = True

                await _set_stage("indexing_es", {"chunk_count": chunk_count})
                await _index_es_nodes(nodes)

                await _set_stage("finalizing", {"chunk_count": chunk_count})

                await doc_repo.update_status(
                    document_id,
                    status=DocumentStatus.COMPLETED,
                    chunk_count=chunk_count,
                    page_count=conversion_result.page_count or 0,
                    content_path=rel_content_path,
                    content_size=content_size,
                    content_format="markdown",
                    error_message=None,
                    processing_stage="completed",
                    processing_meta={"chunk_count": chunk_count},
                )
                await session.commit()
            except Exception as exc:
                logger.exception("Processing failed for %s", document_id)
                await session.rollback()
                if indexed_anything:
                    try:
                        await _delete_document_nodes_async(document_id)
                    except Exception as cleanup_exc:  # noqa: BLE001
                        logger.warning(
                            "Compensation cleanup failed for %s at stage %s: %s",
                            document_id,
                            current_stage,
                            cleanup_exc,
                        )
                await doc_repo.update_status(
                    document_id,
                    status=DocumentStatus.FAILED,
                    error_message=str(exc),
                    processing_stage=current_stage,
                    processing_meta={"failed_stage": current_stage},
                )
                await session.commit()
    finally:
        await close_database()


def _get_embed_model():
    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        _EMBED_MODEL = build_embedding()
    return _EMBED_MODEL


async def _index_pg_nodes(nodes):
    """Index nodes into pgvector."""

    embed_model = _get_embed_model()
    storage_cfg = get_storage_config()

    pg_cfg = storage_cfg.get("postgresql", {})
    provider = get_embedding_provider()
    pgvector_provider_cfg = get_pgvector_config_for_provider(provider)
    pg_config = PGVectorConfig(
        host=pg_cfg.get("host", "localhost"),
        port=pg_cfg.get("port", 5432),
        database=pg_cfg.get("database", "medimind"),
        user=pg_cfg.get("user", "postgres"),
        password=pg_cfg.get("password", ""),
        table_name=pgvector_provider_cfg["table_name"],
        embedding_dimension=pgvector_provider_cfg["embedding_dimension"],
    )
    pg_index = await load_pgvector_index(embed_model, pg_config)
    pg_index.insert_nodes(nodes)  # sync method


async def _index_es_nodes(nodes):
    """Index nodes into Elasticsearch."""

    embed_model = _get_embed_model()
    storage_cfg = get_storage_config()

    es_cfg = storage_cfg.get("elasticsearch", {})
    es_config = ElasticsearchConfig(
        url=es_cfg.get("url", "http://localhost:9200"),
        index_name=es_cfg.get("index_name", "medimind_docs"),
        api_key=es_cfg.get("api_key", None),
        cloud_id=es_cfg.get("cloud_id", None),
    )
    es_index = await load_es_index(embed_model, es_config)
    es_index.insert_nodes(nodes)  # sync method


@app.task(name="medimind_agent.infrastructure.tasks.document_tasks.delete_document_nodes_task")
def delete_document_nodes_task(document_id: str):
    asyncio.run(_delete_document_nodes_async(document_id))


async def _delete_document_nodes_async(document_id: str):
    """Delete vector/ES nodes belonging to a document (best effort)."""
    try:
        global _EMBED_MODEL
        if _EMBED_MODEL is None:
            _EMBED_MODEL = build_embedding()
        embed_model = _EMBED_MODEL
        storage_cfg = get_storage_config()

        pg_cfg = storage_cfg.get("postgresql", {})
        provider = get_embedding_provider()
        pgvector_provider_cfg = get_pgvector_config_for_provider(provider)
        pg_config = PGVectorConfig(
            host=pg_cfg.get("host", "localhost"),
            port=pg_cfg.get("port", 5432),
            database=pg_cfg.get("database", "medimind"),
            user=pg_cfg.get("user", "postgres"),
            password=pg_cfg.get("password", ""),
            table_name=pgvector_provider_cfg["table_name"],
            embedding_dimension=pgvector_provider_cfg["embedding_dimension"],
        )
        try:
            pg_index = await load_pgvector_index(embed_model, pg_config)
            pg_index.delete_ref_doc(document_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Delete pgvector nodes failed for %s: %s", document_id, exc)

        es_cfg = storage_cfg.get("elasticsearch", {})
        es_config = ElasticsearchConfig(
            url=es_cfg.get("url", "http://localhost:9200"),
            index_name=es_cfg.get("index_name", "medimind_docs"),
            api_key=es_cfg.get("api_key", None),
            cloud_id=es_cfg.get("cloud_id", None),
        )
        try:
            es_index = await load_es_index(embed_model, es_config)
            es_index.delete_ref_doc(document_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Delete ES nodes failed for %s: %s", document_id, exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("delete_document_nodes_task failed for %s: %s", document_id, exc)


async def _process_all_pending_async():
    """Helper to process all uploaded/failed/pending documents sequentially."""
    db = await get_database()
    try:
        async with db.session() as session:
            doc_repo = DocumentRepositoryImpl(session)
            pending_docs = []
            for status in (DocumentStatus.UPLOADED, DocumentStatus.FAILED, DocumentStatus.PENDING):
                pending_docs.extend(
                    await doc_repo.list_by_library(limit=1000, offset=0, status=status)
                )
        # Unique by id and pending
        seen = set()
        for doc in pending_docs:
            if doc.document_id in seen:
                continue
            seen.add(doc.document_id)
            if doc.status not in {DocumentStatus.UPLOADED, DocumentStatus.FAILED, DocumentStatus.PENDING}:
                continue
            try:
                await _process_document_async(doc.document_id)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Reprocess pending failed for %s: %s", doc.document_id, exc)
    finally:
        await close_database()


def _load_markdown_nodes(content_path: Path, document: Document):
    """Load markdown file and split into nodes with metadata."""
    reader = MarkdownReader(remove_hyperlinks=False, remove_images=False)
    docs = reader.load_data(
        file=str(content_path),
        extra_info={
            "ref_doc_id": document.document_id,
            "doc_id": document.document_id,
            "document_id": document.document_id,
            "library_id": document.library_id,
            "notebook_id": document.notebook_id,
            "title": document.title,
        },
    )

    nodes = split_documents(docs, chunk_size=512, chunk_overlap=50)
    for idx, node in enumerate(nodes):
        meta = getattr(node, "metadata", {}) or {}
        meta["chunk_index"] = idx
        meta["chunk_id"] = getattr(node, "node_id", "")
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
