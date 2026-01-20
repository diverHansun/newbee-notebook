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
_PG_INDEX = None
_ES_INDEX = None


@app.task(name="medimind_agent.infrastructure.tasks.document_tasks.process_document_task")
def process_document_task(document_id: str):
    asyncio.run(_process_document_async(document_id))


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
                node.metadata = meta
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
    global _EMBED_MODEL, _PG_INDEX, _ES_INDEX
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
    if _PG_INDEX is None:
        _PG_INDEX = await load_pgvector_index(embed_model, pg_config)
    await _PG_INDEX.insert_nodes(nodes)

    # elasticsearch config
    es_cfg = storage_cfg.get("elasticsearch", {})
    es_config = ElasticsearchConfig(
        url=es_cfg.get("url", "http://localhost:9200"),
        index_name=es_cfg.get("index_name", "medimind_docs"),
        api_key=es_cfg.get("api_key", None),
        cloud_id=es_cfg.get("cloud_id", None),
    )
    if _ES_INDEX is None:
        _ES_INDEX = await load_es_index(embed_model, es_config)
    await _ES_INDEX.insert_nodes(nodes)


@app.task(name="medimind_agent.infrastructure.tasks.document_tasks.delete_document_nodes_task")
def delete_document_nodes_task(document_id: str):
    asyncio.run(_delete_document_nodes_async(document_id))


async def _delete_document_nodes_async(document_id: str):
    """Delete vector/ES nodes belonging to a document (best effort)."""
    try:
        global _EMBED_MODEL, _PG_INDEX, _ES_INDEX
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
        if _PG_INDEX is None:
            _PG_INDEX = await load_pgvector_index(embed_model, pg_config)
        try:
            await _PG_INDEX.delete_ref_doc(document_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Delete pgvector nodes failed for %s: %s", document_id, exc)

        es_cfg = storage_cfg.get("elasticsearch", {})
        es_config = ElasticsearchConfig(
            url=es_cfg.get("url", "http://localhost:9200"),
            index_name=es_cfg.get("index_name", "medimind_docs"),
            api_key=es_cfg.get("api_key", None),
            cloud_id=es_cfg.get("cloud_id", None),
        )
        if _ES_INDEX is None:
            _ES_INDEX = await load_es_index(embed_model, es_config)
        try:
            await _ES_INDEX.delete_ref_doc(document_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Delete ES nodes failed for %s: %s", document_id, exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("delete_document_nodes_task failed for %s: %s", document_id, exc)
