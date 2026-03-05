"""
Newbee Notebook - API Dependencies

FastAPI dependency injection configuration.
"""

from typing import AsyncGenerator
import logging
from fastapi import Depends

from newbee_notebook.infrastructure.persistence.database import Database, get_database
from newbee_notebook.infrastructure.persistence.repositories.library_repo_impl import LibraryRepositoryImpl
from newbee_notebook.infrastructure.persistence.repositories.notebook_repo_impl import NotebookRepositoryImpl
from newbee_notebook.infrastructure.persistence.repositories.session_repo_impl import SessionRepositoryImpl
from newbee_notebook.infrastructure.persistence.repositories.document_repo_impl import DocumentRepositoryImpl
from newbee_notebook.infrastructure.persistence.repositories.notebook_document_ref_repo_impl import NotebookDocumentRefRepositoryImpl
from newbee_notebook.infrastructure.persistence.repositories.reference_repo_impl import ReferenceRepositoryImpl
from newbee_notebook.infrastructure.persistence.repositories.message_repo_impl import MessageRepositoryImpl
from newbee_notebook.application.services.library_service import LibraryService
from newbee_notebook.application.services.notebook_service import NotebookService
from newbee_notebook.application.services.session_service import SessionService
from newbee_notebook.application.services.chat_service import ChatService
from newbee_notebook.application.services.document_service import DocumentService
from newbee_notebook.application.services.notebook_document_service import NotebookDocumentService
from newbee_notebook.core.llm import build_llm
from newbee_notebook.core.rag.embeddings import build_embedding
from newbee_notebook.core.engine import load_pgvector_index, load_es_index, SessionManager
from newbee_notebook.core.common.config import (
    get_storage_config,
    get_embedding_provider,
    get_pgvector_config_for_provider,
)
from newbee_notebook.infrastructure.pgvector import PGVectorConfig
from newbee_notebook.infrastructure.elasticsearch import ElasticsearchConfig

logger = logging.getLogger(__name__)


async def get_db_session():
    """Get a database session for the request."""
    db = await get_database()
    async with db.session() as session:
        yield session


# =============================================================================
# Repository Dependencies
# =============================================================================

async def get_library_repo(session=Depends(get_db_session)) -> LibraryRepositoryImpl:
    """Get LibraryRepository instance."""
    return LibraryRepositoryImpl(session)


async def get_notebook_repo(session=Depends(get_db_session)) -> NotebookRepositoryImpl:
    """Get NotebookRepository instance."""
    return NotebookRepositoryImpl(session)


async def get_session_repo(session=Depends(get_db_session)) -> SessionRepositoryImpl:
    """Get SessionRepository instance."""
    return SessionRepositoryImpl(session)

async def get_document_repo(session=Depends(get_db_session)) -> DocumentRepositoryImpl:
    """Get DocumentRepository instance."""
    return DocumentRepositoryImpl(session)


async def get_ref_repo(session=Depends(get_db_session)) -> NotebookDocumentRefRepositoryImpl:
    """Get NotebookDocumentRefRepository instance."""
    return NotebookDocumentRefRepositoryImpl(session)


async def get_reference_repo(session=Depends(get_db_session)) -> ReferenceRepositoryImpl:
    """Get ReferenceRepository instance."""
    return ReferenceRepositoryImpl(session)


async def get_message_repo(session=Depends(get_db_session)) -> MessageRepositoryImpl:
    """Get MessageRepository instance."""
    return MessageRepositoryImpl(session)


# =============================================================================
# Service Dependencies
# =============================================================================

async def get_library_service(
    library_repo: LibraryRepositoryImpl = Depends(get_library_repo),
    document_repo: DocumentRepositoryImpl = Depends(get_document_repo),
    ref_repo: NotebookDocumentRefRepositoryImpl = Depends(get_ref_repo),
) -> LibraryService:
    """
    Get LibraryService instance.
    
    Note: Full implementation would also inject document_repo and ref_repo.
    """
    return LibraryService(
        library_repo=library_repo,
        document_repo=document_repo,
        ref_repo=ref_repo,
    )


async def get_notebook_service(
    notebook_repo: NotebookRepositoryImpl = Depends(get_notebook_repo),
    session_repo: SessionRepositoryImpl = Depends(get_session_repo),
    document_repo: DocumentRepositoryImpl = Depends(get_document_repo),
    ref_repo: NotebookDocumentRefRepositoryImpl = Depends(get_ref_repo),
) -> NotebookService:
    """
    Get NotebookService instance.
    
    Note: Full implementation would also inject document_repo and ref_repo.
    """
    return NotebookService(
        notebook_repo=notebook_repo,
        document_repo=document_repo,
        session_repo=session_repo,
        ref_repo=ref_repo,
    )


async def get_session_service(
    session_repo: SessionRepositoryImpl = Depends(get_session_repo),
    notebook_repo: NotebookRepositoryImpl = Depends(get_notebook_repo),
    message_repo: MessageRepositoryImpl = Depends(get_message_repo),
) -> SessionService:
    """Get SessionService instance."""
    return SessionService(
        session_repo=session_repo,
        notebook_repo=notebook_repo,
        message_repo=message_repo,
    )


# =============================================================================
# Core singletons (LLM, Embedding, Indexes, SessionManager)
# =============================================================================

_llm = None
_embed_model = None
_pgvector_index = None
_es_index = None
_session_manager = None


def get_llm_singleton():
    global _llm
    if _llm is None:
        _llm = build_llm()
    return _llm


def get_embedding_singleton():
    global _embed_model
    if _embed_model is None:
        _embed_model = build_embedding()
    return _embed_model

def reset_llm_singleton() -> None:
    """Reset cached LLM singleton for runtime config changes."""
    global _llm
    _llm = None
    logger.info("LLM singleton reset")


def reset_embedding_singleton() -> None:
    """Reset cached embedding, pgvector, and ES singletons for config changes."""
    global _embed_model, _pgvector_index, _es_index
    _embed_model = None
    _pgvector_index = None
    _es_index = None
    logger.info("Embedding and pgvector singletons reset")


async def get_pg_index_singleton():
    global _pgvector_index
    if _pgvector_index is None:
        storage_cfg = get_storage_config()
        pg_cfg = storage_cfg.get("postgresql", {})
        provider = get_embedding_provider()
        pgvector_provider_cfg = get_pgvector_config_for_provider(provider)
        config = PGVectorConfig(
            host=pg_cfg.get("host", "localhost"),
            port=pg_cfg.get("port", 5432),
            database=pg_cfg.get("database", "newbee_notebook"),
            user=pg_cfg.get("user", "postgres"),
            password=pg_cfg.get("password", ""),
            table_name=pgvector_provider_cfg["table_name"],
            embedding_dimension=pgvector_provider_cfg["embedding_dimension"],
        )
        _pgvector_index = await load_pgvector_index(get_embedding_singleton(), config)
    return _pgvector_index


async def get_es_index_singleton():
    global _es_index
    if _es_index is None:
        storage_cfg = get_storage_config()
        es_cfg = storage_cfg.get("elasticsearch", {})
        config = ElasticsearchConfig(
            url=es_cfg.get("url", "http://localhost:9200"),
            index_name=es_cfg.get("index_name", "newbee_notebook_docs"),
            api_key=es_cfg.get("api_key", None),
            cloud_id=es_cfg.get("cloud_id", None),
        )
        _es_index = await load_es_index(get_embedding_singleton(), config)
    return _es_index


async def get_session_manager_singleton(
    session_repo: SessionRepositoryImpl,
    message_repo: MessageRepositoryImpl,
):
    # Use a fresh LLM client per request. A shared singleton client can leak
    # transport state across aborted stream + immediate fallback requests.
    llm = build_llm()
    pg_index = await get_pg_index_singleton()
    es_index = await get_es_index_singleton()
    return SessionManager(
        llm=llm,
        session_repo=session_repo,
        message_repo=message_repo,
        pgvector_index=pg_index,
        es_index=es_index,
        es_index_name="newbee_notebook_docs",
    )


async def get_session_manager_dep(
    session_repo: SessionRepositoryImpl = Depends(get_session_repo),
    message_repo: MessageRepositoryImpl = Depends(get_message_repo),
) -> SessionManager:
    """Get SessionManager instance for dependency injection."""
    return await get_session_manager_singleton(session_repo, message_repo)


# =============================================================================
# Service Dependencies (continued)
# =============================================================================

async def get_chat_service(
    session_repo: SessionRepositoryImpl = Depends(get_session_repo),
    notebook_repo: NotebookRepositoryImpl = Depends(get_notebook_repo),
    reference_repo: ReferenceRepositoryImpl = Depends(get_reference_repo),
    document_repo: DocumentRepositoryImpl = Depends(get_document_repo),
    ref_repo: NotebookDocumentRefRepositoryImpl = Depends(get_ref_repo),
    message_repo: MessageRepositoryImpl = Depends(get_message_repo),
    session_manager: SessionManager = Depends(get_session_manager_dep),
) -> ChatService:
    """Get ChatService instance."""
    return ChatService(
        session_repo=session_repo,
        notebook_repo=notebook_repo,
        reference_repo=reference_repo,
        document_repo=document_repo,
        ref_repo=ref_repo,
        message_repo=message_repo,
        session_manager=session_manager,
    )


async def get_document_service(
    document_repo: DocumentRepositoryImpl = Depends(get_document_repo),
    library_repo: LibraryRepositoryImpl = Depends(get_library_repo),
    notebook_repo: NotebookRepositoryImpl = Depends(get_notebook_repo),
    ref_repo: NotebookDocumentRefRepositoryImpl = Depends(get_ref_repo),
    reference_repo: ReferenceRepositoryImpl = Depends(get_reference_repo),
) -> DocumentService:
    """Get DocumentService instance."""
    return DocumentService(
        document_repo=document_repo,
        library_repo=library_repo,
        notebook_repo=notebook_repo,
        ref_repo=ref_repo,
        reference_repo=reference_repo,
    )


async def get_notebook_document_service(
    notebook_repo: NotebookRepositoryImpl = Depends(get_notebook_repo),
    document_repo: DocumentRepositoryImpl = Depends(get_document_repo),
    ref_repo: NotebookDocumentRefRepositoryImpl = Depends(get_ref_repo),
) -> NotebookDocumentService:
    """Get NotebookDocumentService instance."""
    return NotebookDocumentService(
        notebook_repo=notebook_repo,
        document_repo=document_repo,
        ref_repo=ref_repo,
    )

