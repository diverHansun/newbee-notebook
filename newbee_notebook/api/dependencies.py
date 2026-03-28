"""
Newbee Notebook - API Dependencies

FastAPI dependency injection configuration.
"""

from pathlib import Path
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
from newbee_notebook.infrastructure.persistence.repositories.mark_repo_impl import MarkRepositoryImpl
from newbee_notebook.infrastructure.persistence.repositories.note_repo_impl import NoteRepositoryImpl
from newbee_notebook.infrastructure.persistence.repositories.diagram_repo_impl import DiagramRepositoryImpl
from newbee_notebook.infrastructure.persistence.repositories.video_summary_repo_impl import (
    VideoSummaryRepositoryImpl,
)
from newbee_notebook.application.services.library_service import LibraryService
from newbee_notebook.application.services.notebook_service import NotebookService
from newbee_notebook.application.services.session_service import SessionService
from newbee_notebook.application.services.chat_service import ChatService
from newbee_notebook.application.services.document_service import DocumentService
from newbee_notebook.application.services.notebook_document_service import NotebookDocumentService
from newbee_notebook.application.services.app_settings_service import AppSettingsService
from newbee_notebook.application.services.mark_service import MarkService
from newbee_notebook.application.services.note_service import NoteService
from newbee_notebook.application.services.diagram_service import DiagramService
from newbee_notebook.application.services.video_service import VideoService
from newbee_notebook.core.llm import build_llm, LLMClientFactory
from newbee_notebook.core.llm.config import resolve_llm_runtime_config
from newbee_notebook.core.mcp import MCPClientManager
from newbee_notebook.core.skills import SkillRegistry
from newbee_notebook.core.rag.embeddings import build_embedding
from newbee_notebook.core.engine import load_pgvector_index, load_es_index
from newbee_notebook.core.engine.confirmation import ConfirmationGateway
from newbee_notebook.core.session import SessionLockManager as RuntimeSessionLockManager
from newbee_notebook.core.session import SessionManager
from newbee_notebook.core.tools import BuiltinToolProvider, ToolRegistry
from newbee_notebook.core.tools.knowledge_base import (
    hybrid_search_executor,
    keyword_search_executor,
    semantic_search_executor,
)
from newbee_notebook.core.common.project_paths import get_configs_directory
from newbee_notebook.core.common.config import (
    get_storage_config,
    get_embedding_provider,
    get_pgvector_config_for_provider,
)
from newbee_notebook.infrastructure.pgvector import PGVectorConfig
from newbee_notebook.infrastructure.elasticsearch import ElasticsearchConfig
from newbee_notebook.infrastructure.storage import get_runtime_storage_backend
from newbee_notebook.infrastructure.storage.base import StorageBackend
from newbee_notebook.infrastructure.bilibili import AsrPipeline, BilibiliAuthManager, BilibiliClient
from newbee_notebook.skills.note import NoteSkillProvider
from newbee_notebook.skills.diagram import DiagramSkillProvider
from newbee_notebook.skills.video import VideoSkillProvider

logger = logging.getLogger(__name__)


def get_storage() -> StorageBackend:
    """Get the runtime storage backend."""
    return get_runtime_storage_backend()


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


async def get_mark_repo(session=Depends(get_db_session)) -> MarkRepositoryImpl:
    """Get MarkRepository instance."""
    return MarkRepositoryImpl(session)


async def get_note_repo(session=Depends(get_db_session)) -> NoteRepositoryImpl:
    """Get NoteRepository instance."""
    return NoteRepositoryImpl(session)


async def get_diagram_repo(session=Depends(get_db_session)) -> DiagramRepositoryImpl:
    """Get DiagramRepository instance."""
    return DiagramRepositoryImpl(session)


async def get_video_repo(session=Depends(get_db_session)) -> VideoSummaryRepositoryImpl:
    """Get VideoSummaryRepository instance."""
    return VideoSummaryRepositoryImpl(session)


def get_app_settings_service(session=Depends(get_db_session)) -> AppSettingsService:
    """Get AppSettingsService instance."""
    return AppSettingsService(session)


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
    diagram_repo: DiagramRepositoryImpl = Depends(get_diagram_repo),
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
        diagram_repo=diagram_repo,
        storage=get_storage(),
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
_llm_client_factory = None
_embed_model = None
_pgvector_index = None
_es_index = None
_runtime_builtin_tool_provider = None
_runtime_tool_registry = None
_runtime_session_lock_manager = None
_mcp_client_manager = None
_runtime_confirmation_gateway = None
_bilibili_auth_manager = None


def get_llm_singleton():
    global _llm
    if _llm is None:
        _llm = build_llm()
    return _llm


def get_llm_client_factory_singleton() -> LLMClientFactory:
    global _llm_client_factory
    if _llm_client_factory is None:
        _llm_client_factory = LLMClientFactory()
    return _llm_client_factory


def get_embedding_singleton():
    global _embed_model
    if _embed_model is None:
        _embed_model = build_embedding()
    return _embed_model


def get_runtime_builtin_tool_provider_singleton() -> BuiltinToolProvider:
    global _runtime_builtin_tool_provider
    if _runtime_builtin_tool_provider is None:
        async def _hybrid_search(payload: dict) -> list[dict]:
            pg_index = await get_pg_index_singleton()
            es_index = await get_es_index_singleton()
            return await hybrid_search_executor(
                payload,
                pgvector_index=pg_index,
                es_index=es_index,
            )

        async def _semantic_search(payload: dict) -> list[dict]:
            pg_index = await get_pg_index_singleton()
            return await semantic_search_executor(
                payload,
                pgvector_index=pg_index,
            )

        async def _keyword_search(payload: dict) -> list[dict]:
            storage_cfg = get_storage_config()
            es_cfg = storage_cfg.get("elasticsearch", {})
            return await keyword_search_executor(
                payload,
                index_name=es_cfg.get("index_name", "newbee_notebook_docs"),
                es_url=es_cfg.get("url", "http://localhost:9200"),
            )

        _runtime_builtin_tool_provider = BuiltinToolProvider(
            hybrid_search=_hybrid_search,
            semantic_search=_semantic_search,
            keyword_search=_keyword_search,
        )
    return _runtime_builtin_tool_provider


def get_runtime_tool_registry_singleton() -> ToolRegistry:
    global _runtime_tool_registry
    if _runtime_tool_registry is None:
        _runtime_tool_registry = ToolRegistry(
            builtin_provider=get_runtime_builtin_tool_provider_singleton(),
            mcp_tool_supplier=get_mcp_client_manager_singleton().list_cached_tools,
        )
    return _runtime_tool_registry


def get_runtime_session_lock_manager_singleton() -> RuntimeSessionLockManager:
    global _runtime_session_lock_manager
    if _runtime_session_lock_manager is None:
        _runtime_session_lock_manager = RuntimeSessionLockManager()
    return _runtime_session_lock_manager


def get_runtime_confirmation_gateway_singleton() -> ConfirmationGateway:
    global _runtime_confirmation_gateway
    if _runtime_confirmation_gateway is None:
        _runtime_confirmation_gateway = ConfirmationGateway()
    return _runtime_confirmation_gateway


def get_mcp_client_manager_singleton() -> MCPClientManager:
    global _mcp_client_manager
    if _mcp_client_manager is None:
        _mcp_client_manager = MCPClientManager(config_path=get_configs_directory() / "mcp.json")
    return _mcp_client_manager


def get_bilibili_auth_manager() -> BilibiliAuthManager:
    global _bilibili_auth_manager
    if _bilibili_auth_manager is None:
        _bilibili_auth_manager = BilibiliAuthManager(base_dir=get_configs_directory())
    return _bilibili_auth_manager

def reset_llm_singleton() -> None:
    """Reset cached LLM singleton for runtime config changes."""
    global _llm, _llm_client_factory
    _llm = None
    if _llm_client_factory is not None:
        _llm_client_factory.reset()
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


async def get_llm_runtime_config_dep(session=Depends(get_db_session)):
    """Resolve the effective runtime LLM config for the current request."""
    return await resolve_llm_runtime_config(session)


async def get_llm_client_dep(
    runtime_config=Depends(get_llm_runtime_config_dep),
):
    """Get the runtime LLM client for the current effective config."""
    factory = get_llm_client_factory_singleton()
    return factory.get_client(runtime_config)


def get_runtime_tool_registry_dep() -> ToolRegistry:
    """Get the new runtime tool registry singleton."""
    return get_runtime_tool_registry_singleton()


def get_confirmation_gateway_dep() -> ConfirmationGateway:
    return get_runtime_confirmation_gateway_singleton()


async def get_mcp_client_manager_dep(
    settings_service: AppSettingsService = Depends(get_app_settings_service),
) -> MCPClientManager:
    manager = get_mcp_client_manager_singleton()
    statuses = await manager.get_server_statuses()
    manager.set_enabled((await settings_service.get("mcp.enabled")) == "true")
    for status in statuses:
        value = await settings_service.get(f"mcp.servers.{status.name}.enabled")
        manager.set_server_enabled(status.name, value != "false")
    await manager.get_tools()
    return manager


async def get_runtime_session_manager_dep(
    session_repo: SessionRepositoryImpl = Depends(get_session_repo),
    message_repo: MessageRepositoryImpl = Depends(get_message_repo),
    runtime_config=Depends(get_llm_runtime_config_dep),
    llm_client=Depends(get_llm_client_dep),
    tool_registry: ToolRegistry = Depends(get_runtime_tool_registry_dep),
    mcp_manager: MCPClientManager = Depends(get_mcp_client_manager_dep),
    confirmation_gateway: ConfirmationGateway = Depends(get_confirmation_gateway_dep),
) -> SessionManager:
    """Get the request-scoped batch-2 runtime session manager."""
    del mcp_manager
    return SessionManager(
        session_repo=session_repo,
        message_repo=message_repo,
        llm_client=llm_client,
        tool_registry=tool_registry,
        lock_manager=get_runtime_session_lock_manager_singleton(),
        confirmation_gateway=confirmation_gateway,
        runtime_config=runtime_config,
    )


async def get_pg_index_dep():
    return await get_pg_index_singleton()


# =============================================================================
# Service Dependencies (continued)
# =============================================================================

async def get_document_service(
    document_repo: DocumentRepositoryImpl = Depends(get_document_repo),
    library_repo: LibraryRepositoryImpl = Depends(get_library_repo),
    notebook_repo: NotebookRepositoryImpl = Depends(get_notebook_repo),
    ref_repo: NotebookDocumentRefRepositoryImpl = Depends(get_ref_repo),
    reference_repo: ReferenceRepositoryImpl = Depends(get_reference_repo),
    diagram_repo: DiagramRepositoryImpl = Depends(get_diagram_repo),
) -> DocumentService:
    """Get DocumentService instance."""
    return DocumentService(
        document_repo=document_repo,
        library_repo=library_repo,
        notebook_repo=notebook_repo,
        ref_repo=ref_repo,
        reference_repo=reference_repo,
        diagram_repo=diagram_repo,
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


async def get_mark_service(
    mark_repo: MarkRepositoryImpl = Depends(get_mark_repo),
    document_repo: DocumentRepositoryImpl = Depends(get_document_repo),
    ref_repo: NotebookDocumentRefRepositoryImpl = Depends(get_ref_repo),
) -> MarkService:
    """Get MarkService instance."""
    return MarkService(
        mark_repo=mark_repo,
        document_repo=document_repo,
        ref_repo=ref_repo,
    )


async def get_note_service(
    note_repo: NoteRepositoryImpl = Depends(get_note_repo),
    ref_repo: NotebookDocumentRefRepositoryImpl = Depends(get_ref_repo),
) -> NoteService:
    """Get NoteService instance."""
    return NoteService(
        note_repo=note_repo,
        ref_repo=ref_repo,
    )


async def get_diagram_service(
    diagram_repo: DiagramRepositoryImpl = Depends(get_diagram_repo),
    ref_repo: NotebookDocumentRefRepositoryImpl = Depends(get_ref_repo),
) -> DiagramService:
    """Get DiagramService instance."""
    return DiagramService(
        diagram_repo=diagram_repo,
        storage=get_storage(),
        ref_repo=ref_repo,
    )


async def get_bilibili_client_dep(
    auth_manager: BilibiliAuthManager = Depends(get_bilibili_auth_manager),
) -> BilibiliClient:
    return BilibiliClient(credential=auth_manager.get_credential())


def get_asr_pipeline_dep() -> AsrPipeline | None:
    return None


async def get_video_service(
    video_repo: VideoSummaryRepositoryImpl = Depends(get_video_repo),
    ref_repo: NotebookDocumentRefRepositoryImpl = Depends(get_ref_repo),
    llm_client=Depends(get_llm_client_dep),
    bili_client: BilibiliClient = Depends(get_bilibili_client_dep),
    asr_pipeline: AsrPipeline | None = Depends(get_asr_pipeline_dep),
) -> VideoService:
    return VideoService(
        video_repo=video_repo,
        bili_client=bili_client,
        llm_client=llm_client,
        storage=get_storage(),
        ref_repo=ref_repo,
        asr_pipeline=asr_pipeline,
    )


async def get_runtime_skill_registry_dep(
    note_service: NoteService = Depends(get_note_service),
    mark_service: MarkService = Depends(get_mark_service),
    diagram_service: DiagramService = Depends(get_diagram_service),
    video_service: VideoService = Depends(get_video_service),
) -> SkillRegistry:
    registry = SkillRegistry()
    registry.register(
        NoteSkillProvider(
            note_service=note_service,
            mark_service=mark_service,
        )
    )
    registry.register(
        DiagramSkillProvider(
            diagram_service=diagram_service,
        )
    )
    registry.register(
        VideoSkillProvider(
            video_service=video_service,
        )
    )
    return registry


async def get_chat_service(
    session_repo: SessionRepositoryImpl = Depends(get_session_repo),
    notebook_repo: NotebookRepositoryImpl = Depends(get_notebook_repo),
    reference_repo: ReferenceRepositoryImpl = Depends(get_reference_repo),
    document_repo: DocumentRepositoryImpl = Depends(get_document_repo),
    ref_repo: NotebookDocumentRefRepositoryImpl = Depends(get_ref_repo),
    message_repo: MessageRepositoryImpl = Depends(get_message_repo),
    session_manager: SessionManager = Depends(get_runtime_session_manager_dep),
    pg_index=Depends(get_pg_index_dep),
    skill_registry: SkillRegistry = Depends(get_runtime_skill_registry_dep),
    confirmation_gateway: ConfirmationGateway = Depends(get_confirmation_gateway_dep),
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
        vector_index=pg_index,
        skill_registry=skill_registry,
        confirmation_gateway=confirmation_gateway,
    )

