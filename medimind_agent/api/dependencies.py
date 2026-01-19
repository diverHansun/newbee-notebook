"""
MediMind Agent - API Dependencies

FastAPI dependency injection configuration.
"""

from typing import AsyncGenerator
from fastapi import Depends

from medimind_agent.infrastructure.persistence.database import Database, get_database
from medimind_agent.infrastructure.persistence.repositories.library_repo_impl import LibraryRepositoryImpl
from medimind_agent.infrastructure.persistence.repositories.notebook_repo_impl import NotebookRepositoryImpl
from medimind_agent.infrastructure.persistence.repositories.session_repo_impl import SessionRepositoryImpl
from medimind_agent.infrastructure.persistence.repositories.document_repo_impl import DocumentRepositoryImpl
from medimind_agent.infrastructure.persistence.repositories.notebook_document_ref_repo_impl import NotebookDocumentRefRepositoryImpl
from medimind_agent.infrastructure.persistence.repositories.reference_repo_impl import ReferenceRepositoryImpl
from medimind_agent.application.services.library_service import LibraryService
from medimind_agent.application.services.notebook_service import NotebookService
from medimind_agent.application.services.session_service import SessionService
from medimind_agent.application.services.chat_service import ChatService
from medimind_agent.application.services.document_service import DocumentService
from medimind_agent.core.llm.zhipu import build_llm
from medimind_agent.core.rag.embeddings import build_embedding
from medimind_agent.core.engine import load_pgvector_index, load_es_index, SessionManager, ModeSelector, ModeType
from medimind_agent.core.common.config import (
    get_storage_config,
    get_embedding_provider,
    get_pgvector_config_for_provider,
)
from medimind_agent.infrastructure.pgvector import PGVectorConfig
from medimind_agent.infrastructure.elasticsearch import ElasticsearchConfig
from medimind_agent.infrastructure.session import ChatSessionStore


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
) -> SessionService:
    """Get SessionService instance."""
    return SessionService(
        session_repo=session_repo,
        notebook_repo=notebook_repo,
    )


async def get_chat_service(
    session_repo: SessionRepositoryImpl = Depends(get_session_repo),
    notebook_repo: NotebookRepositoryImpl = Depends(get_notebook_repo),
    reference_repo: ReferenceRepositoryImpl = Depends(get_reference_repo),
    session_manager: SessionManager = Depends(get_session_manager_dep),
) -> ChatService:
    """Get ChatService instance."""
    return ChatService(
        session_repo=session_repo,
        notebook_repo=notebook_repo,
        reference_repo=reference_repo,
        session_manager=session_manager,
    )


async def get_document_service(
    document_repo: DocumentRepositoryImpl = Depends(get_document_repo),
    library_repo: LibraryRepositoryImpl = Depends(get_library_repo),
    notebook_repo: NotebookRepositoryImpl = Depends(get_notebook_repo),
    ref_repo: NotebookDocumentRefRepositoryImpl = Depends(get_ref_repo),
) -> DocumentService:
    """Get DocumentService instance."""
    return DocumentService(
        document_repo=document_repo,
        library_repo=library_repo,
        notebook_repo=notebook_repo,
        ref_repo=ref_repo,
    )


# =============================================================================
# Core singletons (LLM, Embedding, Indexes, SessionManager)
# =============================================================================

_llm = None
_embed_model = None
_pgvector_index = None
_es_index = None
_session_store = None
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
            database=pg_cfg.get("database", "medimind"),
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
            index_name=es_cfg.get("index_name", "medimind_docs"),
            api_key=es_cfg.get("api_key", None),
            cloud_id=es_cfg.get("cloud_id", None),
        )
        _es_index = await load_es_index(get_embedding_singleton(), config)
    return _es_index


async def get_session_store_singleton():
    global _session_store
    if _session_store is None:
        storage_cfg = get_storage_config()
        pg_cfg = storage_cfg.get("postgresql", {})
        pgvector_cfg = storage_cfg.get("pgvector", {})
        session_cfg = storage_cfg.get("chat_sessions", {})
        session_store_config = PGVectorConfig(
            host=pg_cfg.get("host", "localhost"),
            port=pg_cfg.get("port", 5432),
            database=pg_cfg.get("database", "medimind"),
            user=pg_cfg.get("user", "postgres"),
            password=pg_cfg.get("password", ""),
            table_name=session_cfg.get("table_sessions", "chat_sessions"),
            embedding_dimension=pgvector_cfg.get("embedding_dimension", 1024),
        )
        store = ChatSessionStore(session_store_config)
        await store.initialize()
        _session_store = store
    return _session_store


async def get_session_manager_singleton():
    global _session_manager
    if _session_manager is None:
        llm = get_llm_singleton()
        pg_index = await get_pg_index_singleton()
        es_index = await get_es_index_singleton()
        session_store = await get_session_store_singleton()

        selector = ModeSelector(
            llm=llm,
            pgvector_index=pg_index,
            es_index=es_index,
            memory=None,
            es_index_name="medimind_docs",
        )
        _session_manager = SessionManager(
            llm=llm,
            session_store=session_store,
            pgvector_index=pg_index,
            es_index=es_index,
            es_index_name="medimind_docs",
        )
    return _session_manager


def get_session_manager():
    # thin wrapper to allow sync dependency use; resolve async singleton
    import asyncio
    return asyncio.get_event_loop().run_until_complete(get_session_manager_singleton())


async def get_session_manager_dep() -> SessionManager:
    return await get_session_manager_singleton()


