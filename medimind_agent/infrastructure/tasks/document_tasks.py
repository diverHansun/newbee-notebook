"""
Celery tasks for document processing.
"""

import asyncio
import logging
import os
from pathlib import Path

from medimind_agent.infrastructure.tasks.celery_app import app
from medimind_agent.infrastructure.persistence.database import get_database, close_database
from medimind_agent.infrastructure.persistence.repositories.document_repo_impl import DocumentRepositoryImpl
from medimind_agent.infrastructure.persistence.repositories.notebook_repo_impl import NotebookRepositoryImpl
from medimind_agent.infrastructure.persistence.repositories.library_repo_impl import LibraryRepositoryImpl
from medimind_agent.infrastructure.persistence.repositories.notebook_document_ref_repo_impl import NotebookDocumentRefRepositoryImpl
from medimind_agent.infrastructure.persistence.repositories.reference_repo_impl import ReferenceRepositoryImpl
from medimind_agent.infrastructure.content_extraction.base import get_extractor
from medimind_agent.core.rag.text_splitter.splitter import split_documents
from medimind_agent.core.common.config import (
    get_storage_config,
    get_embedding_provider,
    get_pgvector_config_for_provider,
)
from medimind_agent.core.rag.embeddings import build_embedding
from medimind_agent.core.engine.index_builder import load_pgvector_index, load_es_index
from medimind_agent.core.rag.document_loader.loader import load_documents as loader_load_documents
from medimind_agent.domain.value_objects.document_status import DocumentStatus
from medimind_agent.domain.entities.document import Document
from medimind_agent.infrastructure.pgvector import PGVectorConfig
from medimind_agent.infrastructure.elasticsearch import ElasticsearchConfig
from llama_index.core import Document as LlamaDocument

logger = logging.getLogger(__name__)
_EMBED_MODEL = None


@app.task(name="medimind_agent.infrastructure.tasks.document_tasks.process_document_task")
def process_document_task(document_id: str):
    asyncio.run(_process_document_async(document_id))


@app.task(name="medimind_agent.infrastructure.tasks.document_tasks.process_pending_documents_task")
def process_pending_documents_task():
    """Process all pending documents (utility for resync)."""
    asyncio.run(_process_all_pending_async())


async def _process_document_async(document_id: str):
    db = await get_database()
    async with db.session() as session:
        doc_repo = DocumentRepositoryImpl(session)
        notebook_repo = NotebookRepositoryImpl(session)
        library_repo = LibraryRepositoryImpl(session)
        ref_repo = NotebookDocumentRefRepositoryImpl(session)
        reference_repo = ReferenceRepositoryImpl(session)

        document = await doc_repo.get(document_id)
        if not document:
            logger.error("Document %s not found", document_id)
            return

        try:
            await doc_repo.update_status(document_id, DocumentStatus.PROCESSING, error_message=None)

            text, page_count = _extract_text(document.file_path)

            llama_doc = LlamaDocument(
                text=text,
                metadata={
                    # Align with LlamaIndex defaults
                    "ref_doc_id": document.document_id,
                    "doc_id": document.document_id,
                    # Keep document_id for backward compatibility (will be filtered on ref_doc_id)
                    "document_id": document.document_id,
                    "library_id": document.library_id,
                    "notebook_id": document.notebook_id,
                    "title": document.title,
                },
            )

            nodes = split_documents([llama_doc], chunk_size=512, chunk_overlap=50)
            # annotate chunk_id and chunk_index
            for idx, node in enumerate(nodes):
                meta = getattr(node, "metadata", {}) or {}
                meta["chunk_index"] = idx
                meta["chunk_id"] = getattr(node, "node_id", "")
                # propagate doc id aliases for downstream filters
                meta["ref_doc_id"] = document.document_id
                meta["doc_id"] = document.document_id
                meta["document_id"] = document.document_id
                node.metadata = meta
                # LlamaIndex uses node.ref_doc_id to populate metadata.ref_doc_id; set explicitly
                try:
                    node.ref_doc_id = document.document_id
                    node.doc_id = document.document_id
                except Exception:
                    # fallback: best effort, do not block indexing
                    pass
            chunk_count = len(nodes)

            # Index into pgvector and elasticsearch
            await _index_nodes(nodes)

            await doc_repo.update_status(
                document_id,
                status=DocumentStatus.COMPLETED,
                chunk_count=chunk_count,
                page_count=page_count,
                error_message=None,
            )
        except Exception as exc:
            logger.exception("Processing failed for %s", document_id)
            await doc_repo.update_status(
                document_id,
                status=DocumentStatus.FAILED,
                error_message=str(exc),
            )
    await close_database()


def _extract_text(path: str):
    extractor = get_extractor(path)
    result = extractor.extract(path)
    return result.text, result.page_count


async def _index_nodes(nodes):
    """Index nodes into pgvector and Elasticsearch.

    Note: indices are re-initialized per call to avoid event-loop coupling
    between tasks (aiohttp clients are bound to the loop that created them).
    """

    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        _EMBED_MODEL = build_embedding()
    embed_model = _EMBED_MODEL
    storage_cfg = get_storage_config()

    # pgvector config
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

    # elasticsearch config
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
            await pg_index.delete_ref_doc(document_id)
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
            await es_index.delete_ref_doc(document_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Delete ES nodes failed for %s: %s", document_id, exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("delete_document_nodes_task failed for %s: %s", document_id, exc)


async def _process_all_pending_async():
    """Helper to process all pending documents sequentially."""
    db = await get_database()
    async with db.session() as session:
        doc_repo = DocumentRepositoryImpl(session)
        # Fetch pending documents
        pending_docs = await doc_repo.list_by_library(limit=1000, offset=0, status=DocumentStatus.PENDING)
        # Include notebook docs
        notebooks = await NotebookRepositoryImpl(session).list(limit=1000, offset=0)
        for nb in notebooks:
            pending_docs.extend(
                await doc_repo.list_by_notebook(nb.notebook_id, limit=1000, offset=0)
            )
        # Unique by id and pending
        seen = set()
        for doc in pending_docs:
            if doc.document_id in seen:
                continue
            seen.add(doc.document_id)
            if doc.status != DocumentStatus.PENDING:
                continue
            try:
                await _process_document_async(doc.document_id)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Reprocess pending failed for %s: %s", doc.document_id, exc)
    await close_database()
