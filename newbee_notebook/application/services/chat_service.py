"""
Newbee Notebook - Chat Service

Application service for chat operations.
"""

from datetime import datetime
from typing import Optional, List, AsyncGenerator, Dict, Any, Awaitable, Callable
import asyncio
import logging
import re
from dataclasses import dataclass, field
from dataclasses import asdict

from newbee_notebook.core.common.config_db import resolve_llm_api_key
from newbee_notebook.domain.entities.session import Session
from newbee_notebook.domain.value_objects.mode_type import (
    ModeType,
    MessageRole,
    normalize_runtime_mode,
)
from newbee_notebook.domain.repositories.session_repository import SessionRepository
from newbee_notebook.domain.repositories.notebook_repository import NotebookRepository
from newbee_notebook.domain.repositories.reference_repository import (
    ReferenceRepository,
    NotebookDocumentRefRepository,
)
from newbee_notebook.domain.repositories.document_repository import DocumentRepository
from newbee_notebook.domain.repositories.generated_image_repository import (
    GeneratedImageRepository,
)
from newbee_notebook.domain.repositories.message_repository import MessageRepository
from newbee_notebook.domain.entities.generated_image import GeneratedImage
from newbee_notebook.domain.entities.reference import Reference
from newbee_notebook.domain.entities.message import Message
from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.core.engine.stream_events import (
    ConfirmationRequestEvent,
    ContentEvent,
    DoneEvent,
    ErrorEvent,
    ImageGeneratedEvent,
    IntermediateContentEvent,
    PhaseEvent,
    SourceEvent,
    StartEvent,
    ToolCallEvent,
    ToolResultEvent,
    WarningEvent,
)
from newbee_notebook.core.skills import SkillContext, SkillRegistry
from newbee_notebook.core.session import SessionManager
from newbee_notebook.core.tools.contracts import ToolDefinition
from newbee_notebook.core.tools.image_generation import (
    ImageToolContext,
    build_image_generation_tool,
)
from newbee_notebook.core.common.node_utils import extract_document_id
from newbee_notebook.exceptions import DocumentProcessingError
from newbee_notebook.core.engine.confirmation import ConfirmationGateway
from newbee_notebook.infrastructure.storage import get_runtime_storage_backend
from newbee_notebook.infrastructure.storage.base import StorageBackend


logger = logging.getLogger(__name__)
STREAM_CHUNK_TIMEOUT_SECONDS_DEFAULT = 60
STREAM_CHUNK_TIMEOUT_SECONDS_COMPLEX_MODES = 180
ASK_SOURCE_SCORE_THRESHOLD = 0.3
REMOTE_MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*]\(https?://[^)\s]+\)")
REMOTE_HTML_IMAGE_PATTERN = re.compile(
    r"<img\b[^>]*src=['\"]https?://[^'\"]+['\"][^>]*>",
    flags=re.IGNORECASE,
)
EXCESS_BLANK_LINES_PATTERN = re.compile(r"\n{3,}")


@dataclass
class ChatSource:
    """Reference source from RAG retrieval."""

    document_id: str
    chunk_id: str
    title: str
    content: str
    score: float = 0.0


@dataclass
class ChatResult:
    """Result of a chat completion."""

    session_id: str
    message_id: int
    content: str
    mode: ModeType
    sources: List[ChatSource]
    images: List[dict] = field(default_factory=list)
    warnings: List[dict] = field(default_factory=list)


class ChatService:
    """
    Application service for chat operations.

    Responsibilities:
    - Orchestrate the chat flow
    - Manage session context
    - Integrate with RAG retrieval
    - Handle streaming responses
    """

    def __init__(
        self,
        session_repo: SessionRepository,
        notebook_repo: NotebookRepository,
        reference_repo: ReferenceRepository,
        document_repo: DocumentRepository,
        ref_repo: NotebookDocumentRefRepository,
        message_repo: MessageRepository,
        session_manager: SessionManager,
        generated_image_repo: GeneratedImageRepository | None = None,
        storage: StorageBackend | None = None,
        vector_index: Any = None,
        vector_index_loader: Callable[[], Awaitable[Any]] | None = None,
        skill_registry: SkillRegistry | None = None,
        confirmation_gateway: ConfirmationGateway | None = None,
    ):
        self._session_repo = session_repo
        self._notebook_repo = notebook_repo
        self._reference_repo = reference_repo
        self._document_repo = document_repo
        self._ref_repo = ref_repo
        self._message_repo = message_repo
        self._session_manager = session_manager
        self._generated_image_repo = generated_image_repo
        self._storage = storage
        self._vector_index = vector_index
        self._vector_index_loader = vector_index_loader
        self._skill_registry = skill_registry
        self._confirmation_gateway = confirmation_gateway

    @staticmethod
    def _source_items_to_dicts(items: List[Any]) -> List[dict]:
        normalized: List[dict] = []
        for item in items or []:
            if isinstance(item, dict):
                normalized.append(item)
            else:
                normalized.append(asdict(item))
        return normalized

    @staticmethod
    def _image_items_to_dicts(items: List[Any]) -> List[dict]:
        normalized: List[dict] = []
        for item in items or []:
            if isinstance(item, dict):
                normalized.append(item)
            else:
                normalized.append(asdict(item))
        return normalized

    @staticmethod
    def _image_ids(items: List[Any]) -> List[str]:
        image_ids: List[str] = []
        for item in items or []:
            if isinstance(item, dict):
                image_id = str(item.get("image_id") or "").strip()
            else:
                image_id = str(getattr(item, "image_id", "") or "").strip()
            if image_id:
                image_ids.append(image_id)
        return image_ids

    @staticmethod
    def _strip_generated_image_markup(content: str, images: List[Any] | None) -> str:
        normalized = str(content or "")
        if not normalized.strip() or not images:
            return normalized
        cleaned = REMOTE_MARKDOWN_IMAGE_PATTERN.sub("", normalized)
        cleaned = REMOTE_HTML_IMAGE_PATTERN.sub("", cleaned)
        cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
        cleaned = EXCESS_BLANK_LINES_PATTERN.sub("\n\n", cleaned).strip()
        return cleaned

    async def _persist_generated_image_record(self, **kwargs: Any) -> None:
        if self._generated_image_repo is None:
            return
        image = GeneratedImage(
            image_id=str(kwargs.get("image_id") or ""),
            session_id=str(kwargs.get("session_id") or ""),
            notebook_id=str(kwargs.get("notebook_id") or ""),
            message_id=kwargs.get("message_id"),
            tool_call_id=str(kwargs.get("tool_call_id") or ""),
            prompt=str(kwargs.get("prompt") or ""),
            provider=str(kwargs.get("provider") or ""),
            model=str(kwargs.get("model") or ""),
            size=str(kwargs.get("size") or "") or None,
            width=kwargs.get("width"),
            height=kwargs.get("height"),
            storage_key=str(kwargs.get("storage_key") or ""),
            file_size=int(kwargs.get("file_size") or 0),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        await self._generated_image_repo.create(image)

    async def _backfill_generated_images_message_id(
        self,
        *,
        image_ids: List[str],
        message_id: int,
    ) -> None:
        if self._generated_image_repo is None:
            return
        for image_id in image_ids:
            await self._generated_image_repo.update_message_id(image_id, message_id)

    def _resolve_storage_backend(self) -> StorageBackend | None:
        if self._storage is not None:
            return self._storage
        try:
            self._storage = get_runtime_storage_backend()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Skipping image_generate tool because storage backend is unavailable: %s",
                exc,
            )
            return None
        return self._storage

    def _build_image_tool_for_runtime(
        self,
        *,
        mode: ModeType,
        session_id: str,
        notebook_id: str,
    ) -> ToolDefinition | None:
        if mode not in {ModeType.AGENT, ModeType.ASK}:
            return None
        if self._generated_image_repo is None:
            return None
        storage = self._resolve_storage_backend()
        if storage is None:
            return None

        runtime_config = getattr(self._session_manager, "runtime_config", None)
        provider = str(getattr(runtime_config, "provider", "") or "").strip().lower()
        if provider not in {"qwen", "zhipu"}:
            return None
        api_key = str(resolve_llm_api_key(provider) or "").strip()
        if not api_key:
            logger.warning(
                "Skipping image_generate tool because API key for provider '%s' is not configured.",
                provider,
            )
            return None

        context = ImageToolContext(
            session_id=session_id,
            notebook_id=notebook_id,
            provider=provider,
            api_key=api_key,
            storage=storage,
            save_record=self._persist_generated_image_record,
        )
        return build_image_generation_tool(context)

    def _merge_external_tools_with_image_tool(
        self,
        *,
        mode: ModeType,
        session_id: str,
        notebook_id: str,
        external_tools: list[Any] | None,
    ) -> list[Any] | None:
        merged = list(external_tools or [])
        image_tool = self._build_image_tool_for_runtime(
            mode=mode,
            session_id=session_id,
            notebook_id=notebook_id,
        )
        if image_tool and not any(
            str(getattr(tool, "name", "") or "").strip() == image_tool.name
            for tool in merged
        ):
            merged.append(image_tool)
        return merged or None

    @staticmethod
    def _get_stream_chunk_timeout_seconds(mode: ModeType) -> int:
        # explain/conclude requests may have a longer retrieval/prompting gap
        # before the first token arrives on some providers (e.g. qwen).
        if mode in {ModeType.EXPLAIN, ModeType.CONCLUDE}:
            return STREAM_CHUNK_TIMEOUT_SECONDS_COMPLEX_MODES
        return STREAM_CHUNK_TIMEOUT_SECONDS_DEFAULT

    async def _get_vector_index(self):
        if self._vector_index is not None:
            return self._vector_index
        if self._vector_index_loader is None:
            return None
        self._vector_index = await self._vector_index_loader()
        return self._vector_index

    async def chat(
        self,
        session_id: str,
        message: str,
        mode: str = "chat",
        context: Optional[dict] = None,
        include_ec_context: Optional[bool] = None,
        source_document_ids: Optional[List[str]] = None,
        lang: str = "en",
    ) -> ChatResult:
        """
        Send a message and get a complete response.

        Args:
            session_id: Session ID.
            message: User message.
            mode: Chat mode (chat, ask, explain, conclude).

        Returns:
            ChatResult with response and sources.
        """
        # Get session
        session = await self._session_repo.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        mode_enum = ModeType(mode)
        effective_include_ec_context = (
            include_ec_context
            if include_ec_context is not None
            else bool(getattr(session, "include_ec_context", False))
        )

        runtime_mode_enum = normalize_runtime_mode(mode_enum)
        await self._session_manager.start_session(session_id=session_id)
        (
            runtime_message,
            runtime_mode_enum,
            external_tools,
            system_prompt_addition,
            confirmation_required,
            confirmation_meta,
            force_first_tool_call,
            required_tool_call_before_response,
        ) = self._resolve_skill_runtime(
            notebook_id=session.notebook_id,
            message=message,
            runtime_mode=runtime_mode_enum,
            source_document_ids=source_document_ids,
        )
        mode_enum = runtime_mode_enum
        external_tools = self._merge_external_tools_with_image_tool(
            mode=runtime_mode_enum,
            session_id=session_id,
            notebook_id=session.notebook_id,
            external_tools=external_tools,
        )

        # Notebook scope documents
        (
            allowed_doc_ids,
            docs_by_status,
            blocking_doc_ids,
            completed_doc_titles,
        ) = await self._get_notebook_scope(session.notebook_id)
        allowed_doc_ids = self._apply_source_filter(
            allowed_doc_ids, source_document_ids
        )
        allowed_doc_id_set = set(allowed_doc_ids)
        filtered_doc_titles = {
            doc_id: title
            for doc_id, title in completed_doc_titles.items()
            if doc_id in allowed_doc_id_set
        }
        warnings: List[dict] = []
        mode_context = self._build_mode_context(context, filtered_doc_titles)
        if mode_enum in {ModeType.CONCLUDE, ModeType.EXPLAIN}:
            await self._validate_mode_guard(
                mode_enum=mode_enum,
                allowed_doc_ids=allowed_doc_ids,
                context=context,
                notebook_id=session.notebook_id,
                documents_by_status=docs_by_status,
                blocking_document_ids=blocking_doc_ids,
            )
        blocking_warning = self._build_blocking_warning(
            blocking_doc_ids=blocking_doc_ids,
            allowed_doc_ids=allowed_doc_ids,
            docs_by_status=docs_by_status,
        )
        if runtime_mode_enum is not ModeType.AGENT and blocking_warning:
            warnings.append(blocking_warning)

        # Fetch context-based chunks (used for sources/references)
        context_chunks = await self._get_context_chunks(context) if context else []

        runtime_result = await self._session_manager.chat(
            message=runtime_message,
            mode_type=runtime_mode_enum,
            allowed_document_ids=allowed_doc_ids,
            context=mode_context,
            include_ec_context=effective_include_ec_context,
            external_tools=external_tools,
            system_prompt_addition=system_prompt_addition,
            confirmation_required=confirmation_required,
            confirmation_meta=confirmation_meta,
            force_first_tool_call=force_first_tool_call,
            required_tool_call_before_response=required_tool_call_before_response,
            confirmation_gateway=self._confirmation_gateway,
            lang=lang,
        )
        response_content = self._strip_generated_image_markup(
            runtime_result.content,
            runtime_result.images,
        )
        sources = self._source_items_to_dicts(runtime_result.sources)
        images = self._image_items_to_dicts(runtime_result.images)
        image_ids = list(dict.fromkeys(self._image_ids(runtime_result.images)))
        warnings.extend(runtime_result.warnings)
        message_id = session.message_count + 1

        # Persist messages
        user_msg = Message(
            session_id=session_id,
            mode=runtime_mode_enum,
            role=MessageRole.USER,
            content=message,
        )
        assistant_msg = Message(
            session_id=session_id,
            mode=runtime_mode_enum,
            role=MessageRole.ASSISTANT,
            content=response_content,
        )
        await self._message_repo.create_batch([user_msg, assistant_msg])
        await self._session_repo.increment_message_count(session_id, 2)
        assistant_message_id = (
            int(assistant_msg.message_id)
            if isinstance(assistant_msg.message_id, int)
            else None
        )
        if image_ids and assistant_message_id is not None:
            try:
                await self._backfill_generated_images_message_id(
                    image_ids=image_ids,
                    message_id=assistant_message_id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to backfill generated image message_id for session %s: %s",
                    session_id,
                    exc,
                )

        # Merge sources with user selection/context chunks for consistency
        sources = self._merge_sources_with_context(
            sources or [], context, context_chunks
        )
        sources_before_validation = list(sources)
        sources = await self._filter_valid_sources(sources)
        sources = self._filter_sources_by_mode_quality(sources, mode_enum)
        sources = self._restore_ask_display_sources_if_empty(
            sources=sources,
            prevalidated_sources=sources_before_validation,
            mode_enum=mode_enum,
        )

        if sources:
            refs = [
                Reference(
                    session_id=session_id,
                    message_id=message_id,
                    document_id=src.get("document_id"),
                    chunk_id=src.get("chunk_id", ""),
                    quoted_text=src.get("text", "")[:2000],
                    context=None,
                )
                for src in sources
                if src.get("document_id")
            ]
            if refs:
                await self._reference_repo.create_batch(refs)

        return ChatResult(
            session_id=session_id,
            message_id=message_id,
            content=response_content,
            mode=runtime_mode_enum,
            sources=[
                ChatSource(
                    document_id=s.get("document_id"),
                    chunk_id=s.get("chunk_id", ""),
                    title=s.get("title", ""),
                    content=s.get("text", ""),
                    score=s.get("score", 0.0),
                )
                for s in sources
            ],
            images=images,
            warnings=warnings,
        )

    async def chat_stream(
        self,
        session_id: str,
        message: str,
        mode: str = "chat",
        context: Optional[dict] = None,
        include_ec_context: Optional[bool] = None,
        source_document_ids: Optional[List[str]] = None,
        lang: str = "en",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send a message and stream the response.

        This method uses true LLM streaming to provide real-time token-by-token
        response generation.

        Args:
            session_id: Session ID.
            message: User message.
            mode: Chat mode.
            context: Optional context (e.g., selected text).

        Yields:
            Event dictionaries with type and data:
            - {"type": "start", "message_id": int}
            - {"type": "phase", "stage": str}
            - {"type": "content", "delta": str}
            - {"type": "sources", "sources": list}
            - {"type": "done"}
            - {"type": "error", "error_code": str, "message": str}
        """
        session = await self._session_repo.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        mode_enum = ModeType(mode)
        runtime_mode_enum = normalize_runtime_mode(mode_enum)
        effective_include_ec_context = (
            include_ec_context
            if include_ec_context is not None
            else bool(getattr(session, "include_ec_context", False))
        )
        await self._session_manager.start_session(session_id=session_id)
        (
            runtime_message,
            runtime_mode_enum,
            external_tools,
            system_prompt_addition,
            confirmation_required,
            confirmation_meta,
            force_first_tool_call,
            required_tool_call_before_response,
        ) = self._resolve_skill_runtime(
            notebook_id=session.notebook_id,
            message=message,
            runtime_mode=runtime_mode_enum,
            source_document_ids=source_document_ids,
        )
        mode_enum = runtime_mode_enum
        external_tools = self._merge_external_tools_with_image_tool(
            mode=runtime_mode_enum,
            session_id=session_id,
            notebook_id=session.notebook_id,
            external_tools=external_tools,
        )
        (
            allowed_doc_ids,
            docs_by_status,
            blocking_doc_ids,
            completed_doc_titles,
        ) = await self._get_notebook_scope(session.notebook_id)
        allowed_doc_ids = self._apply_source_filter(
            allowed_doc_ids, source_document_ids
        )
        allowed_doc_id_set = set(allowed_doc_ids)
        filtered_doc_titles = {
            doc_id: title
            for doc_id, title in completed_doc_titles.items()
            if doc_id in allowed_doc_id_set
        }
        mode_context = self._build_mode_context(context, filtered_doc_titles)
        if mode_enum in {ModeType.CONCLUDE, ModeType.EXPLAIN}:
            await self._validate_mode_guard(
                mode_enum=mode_enum,
                allowed_doc_ids=allowed_doc_ids,
                context=context,
                notebook_id=session.notebook_id,
                documents_by_status=docs_by_status,
                blocking_document_ids=blocking_doc_ids,
            )

        message_id = session.message_count + 1

        yield {"type": "start", "message_id": message_id}
        blocking_warning = self._build_blocking_warning(
            blocking_doc_ids=blocking_doc_ids,
            allowed_doc_ids=allowed_doc_ids,
            docs_by_status=docs_by_status,
        )
        if runtime_mode_enum is not ModeType.AGENT and blocking_warning:
            yield blocking_warning

        full_response = ""
        sources: List[dict] = []
        generated_image_ids: list[str] = []
        context_chunks = await self._get_context_chunks(context) if context else []
        stream_ready_to_finish = False
        stream = None

        try:
            stream = self._session_manager.chat_stream(
                message=runtime_message,
                mode_type=runtime_mode_enum,
                allowed_document_ids=allowed_doc_ids,
                context=mode_context,
                include_ec_context=effective_include_ec_context,
                external_tools=external_tools,
                system_prompt_addition=system_prompt_addition,
                confirmation_required=confirmation_required,
                confirmation_meta=confirmation_meta,
                force_first_tool_call=force_first_tool_call,
                required_tool_call_before_response=required_tool_call_before_response,
                confirmation_gateway=self._confirmation_gateway,
                lang=lang,
            )
            while True:
                try:
                    event = await asyncio.wait_for(
                        stream.__anext__(),
                        timeout=self._get_stream_chunk_timeout_seconds(mode_enum),
                    )
                except StopAsyncIteration:
                    break

                if isinstance(event, StartEvent):
                    continue
                if isinstance(event, WarningEvent):
                    yield {
                        "type": "warning",
                        "code": event.code,
                        "message": event.message,
                    }
                    continue
                if isinstance(event, PhaseEvent):
                    yield {"type": "phase", "stage": event.stage}
                    continue
                if isinstance(event, IntermediateContentEvent):
                    yield {"type": "intermediate_content", "delta": event.delta}
                    continue
                if isinstance(event, ToolCallEvent):
                    yield {
                        "type": "tool_call",
                        "tool_name": event.tool_name,
                        "tool_call_id": event.tool_call_id,
                        "tool_input": event.tool_input,
                    }
                    continue
                if isinstance(event, ToolResultEvent):
                    yield {
                        "type": "tool_result",
                        "tool_name": event.tool_name,
                        "tool_call_id": event.tool_call_id,
                        "success": event.success,
                        "content_preview": event.content_preview,
                        "quality_meta": asdict(event.quality_meta)
                        if event.quality_meta
                        else None,
                    }
                    continue
                if isinstance(event, ImageGeneratedEvent):
                    normalized_images = self._image_items_to_dicts(event.images)
                    generated_image_ids.extend(self._image_ids(event.images))
                    yield {
                        "type": "image_generated",
                        "images": normalized_images,
                        "tool_call_id": event.tool_call_id,
                        "tool_name": event.tool_name,
                    }
                    continue
                if isinstance(event, ConfirmationRequestEvent):
                    yield {
                        "type": "confirmation_request",
                        "request_id": event.request_id,
                        "tool_name": event.tool_name,
                        "action_type": event.action_type,
                        "target_type": event.target_type,
                        "args_summary": event.args_summary,
                        "description": event.description,
                    }
                    continue
                if isinstance(event, ContentEvent):
                    full_response += event.delta
                    yield {"type": "content", "delta": event.delta}
                    continue
                if isinstance(event, SourceEvent):
                    sources = self._merge_sources_with_context(
                        self._source_items_to_dicts(event.sources),
                        context,
                        context_chunks,
                    )
                    continue
                if isinstance(event, DoneEvent):
                    break
                if isinstance(event, ErrorEvent):
                    yield {
                        "type": "error",
                        "error_code": event.code,
                        "message": event.message,
                    }
                    return
            sources_before_validation = list(sources)
            sources = await self._filter_valid_sources(sources)
            sources = self._filter_sources_by_mode_quality(sources, mode_enum)
            sources = self._restore_ask_display_sources_if_empty(
                sources=sources,
                prevalidated_sources=sources_before_validation,
                mode_enum=mode_enum,
            )

            if sources:
                yield {
                    "type": "sources",
                    "sources": sources,
                    "sources_type": self._resolve_sources_type(sources),
                }

            # Persist messages before "done" so client-side connection close does not
            # race with database writes and cause missing chat history.
            user_msg = Message(
                session_id=session_id,
                mode=runtime_mode_enum,
                role=MessageRole.USER,
                content=message,
            )
            sanitized_full_response = self._strip_generated_image_markup(
                full_response,
                generated_image_ids,
            )
            assistant_msg = Message(
                session_id=session_id,
                mode=runtime_mode_enum,
                role=MessageRole.ASSISTANT,
                content=sanitized_full_response,
            )
            await self._message_repo.create_batch([user_msg, assistant_msg])
            await self._session_repo.increment_message_count(session_id, 2)
            assistant_message_id = (
                int(assistant_msg.message_id)
                if isinstance(assistant_msg.message_id, int)
                else None
            )
            unique_generated_image_ids = list(dict.fromkeys(generated_image_ids))
            if unique_generated_image_ids and assistant_message_id is not None:
                try:
                    await self._backfill_generated_images_message_id(
                        image_ids=unique_generated_image_ids,
                        message_id=assistant_message_id,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Failed to backfill generated image message_id in stream for session %s: %s",
                        session_id,
                        exc,
                    )

            # Persist references
            if sources:
                refs = [
                    Reference(
                        session_id=session_id,
                        message_id=message_id,
                        document_id=s.get("document_id"),
                        chunk_id=s.get("chunk_id", ""),
                        quoted_text=s.get("text", "")[:2000],
                        context=None,
                    )
                    for s in sources
                    if s.get("document_id")
                ]
                if refs:
                    await self._reference_repo.create_batch(refs)

            # Mark completion before yielding "done" so a client-side connection
            # close immediately after receiving the event is treated as normal.
            stream_ready_to_finish = True
            yield {"type": "done"}

        except asyncio.TimeoutError:
            yield {
                "type": "error",
                "error_code": "timeout",
                "message": "Stream timeout",
            }
        except asyncio.CancelledError:
            if stream is not None:
                try:
                    await stream.aclose()
                except Exception:
                    logger.debug(
                        "Failed to close upstream stream cleanly for session %s",
                        session_id,
                    )
            if stream_ready_to_finish:
                logger.debug(
                    "Stream connection closed after completion for session %s",
                    session_id,
                )
            else:
                logger.info(
                    "Stream cancelled before completion for session %s", session_id
                )
            return
        except DocumentProcessingError as exc:
            payload = {
                "type": "error",
                "error_code": exc.error_code,
                "message": exc.message,
            }
            if exc.details:
                payload["details"] = exc.details
            yield payload
        except Exception as exc:
            logger.error(f"Stream error for session {session_id}: {exc}")
            yield {"type": "error", "error_code": "internal_error", "message": str(exc)}

    def _resolve_skill_runtime(
        self,
        *,
        notebook_id: str,
        message: str,
        runtime_mode: ModeType,
        source_document_ids: Optional[List[str]],
    ) -> tuple[
        str,
        ModeType,
        list[Any] | None,
        str,
        frozenset[str],
        dict,
        bool,
        str | frozenset[str] | None,
    ]:
        if not self._skill_registry:
            return message, runtime_mode, None, "", frozenset(), {}, False, None

        matched = self._skill_registry.match_command(message)
        if not matched:
            return message, runtime_mode, None, "", frozenset(), {}, False, None

        provider, activated_command, cleaned_message = matched
        manifest = provider.build_manifest(
            SkillContext(
                notebook_id=notebook_id,
                activated_command=activated_command,
                selected_document_ids=list(source_document_ids or []),
                request_message=cleaned_message,
            )
        )
        return (
            cleaned_message,
            ModeType.AGENT,
            list(manifest.tools),
            manifest.system_prompt_addition,
            manifest.confirmation_required,
            manifest.confirmation_meta,
            manifest.force_first_tool_call,
            manifest.required_tool_call_before_response,
        )

    async def confirm_action(
        self, session_id: str, request_id: str, approved: bool
    ) -> bool:
        session = await self._session_repo.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        if not self._confirmation_gateway:
            return False
        return bool(self._confirmation_gateway.resolve(request_id, approved))

    async def prevalidate_mode_requirements(
        self,
        session_id: str,
        mode: str,
        context: Optional[dict] = None,
    ) -> None:
        """Validate requirements for conclude/explain before streaming responses."""
        session = await self._session_repo.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        (
            allowed_doc_ids,
            docs_by_status,
            blocking_doc_ids,
            _,
        ) = await self._get_notebook_scope(session.notebook_id)
        mode_enum = ModeType(mode)
        if mode_enum in {ModeType.CHAT, ModeType.AGENT, ModeType.ASK}:
            return
        await self._validate_mode_guard(
            mode_enum=mode_enum,
            allowed_doc_ids=allowed_doc_ids,
            context=context,
            notebook_id=session.notebook_id,
            documents_by_status=docs_by_status,
            blocking_document_ids=blocking_doc_ids,
        )

    async def _validate_mode_guard(
        self,
        mode_enum: ModeType,
        allowed_doc_ids: List[str],
        context: Optional[dict],
        notebook_id: Optional[str] = None,
        documents_by_status: Optional[Dict[str, int]] = None,
        blocking_document_ids: Optional[List[str]] = None,
    ) -> None:
        """Common guard for retrieval-dependent modes."""
        rag_modes = (ModeType.CONCLUDE, ModeType.EXPLAIN)
        if (
            mode_enum in rag_modes
            and not allowed_doc_ids
            and (blocking_document_ids or [])
        ):
            raise DocumentProcessingError(
                message="All documents are still processing; no searchable data is available yet.",
                details={
                    "mode": mode_enum.value,
                    "notebook_id": notebook_id,
                    "blocking_document_ids": blocking_document_ids or [],
                    "documents_by_status": documents_by_status or {},
                    "retryable": True,
                },
            )

        if mode_enum in (ModeType.CONCLUDE, ModeType.EXPLAIN):
            if not allowed_doc_ids and not (context and context.get("selected_text")):
                raise ValueError(
                    "Conclude/Explain mode requires at least one processed document "
                    "or a selected_text context."
                )
            if (
                context
                and context.get("selected_text")
                and not context.get("document_id")
            ):
                raise ValueError(
                    "selected_text requires a document_id to ensure traceable sources"
                )
            if context and context.get("document_id"):
                target_doc_id = context["document_id"]
                if target_doc_id not in set(allowed_doc_ids):
                    raise DocumentProcessingError(
                        message="This document index is not ready yet, so explain/conclude is unavailable.",
                        details={
                            "mode": mode_enum.value,
                            "document_id": target_doc_id,
                            "retryable": True,
                        },
                    )

    @staticmethod
    def _apply_source_filter(
        all_doc_ids: List[str],
        source_document_ids: Optional[List[str]],
    ) -> List[str]:
        """Apply user-selected source filtering at the notebook scope boundary."""
        if source_document_ids is None:
            return all_doc_ids
        valid_set = set(all_doc_ids)
        filtered = [doc_id for doc_id in source_document_ids if doc_id in valid_set]
        excluded = [doc_id for doc_id in source_document_ids if doc_id not in valid_set]
        if excluded:
            logger.info(
                "source_document_ids filter excluded %d non-completed doc(s): %s",
                len(excluded),
                excluded,
            )
        return filtered

    @staticmethod
    def _build_blocking_warning(
        blocking_doc_ids: List[str],
        allowed_doc_ids: List[str],
        docs_by_status: Dict[str, int],
    ) -> Optional[Dict[str, Any]]:
        if not blocking_doc_ids or not allowed_doc_ids:
            return None
        return {
            "type": "warning",
            "code": "partial_documents",
            "message": (
                f"{len(blocking_doc_ids)} document(s) are still processing; "
                "the current retrieval scope excludes them."
            ),
            "details": {
                "blocking_document_ids": blocking_doc_ids,
                "available_document_count": len(allowed_doc_ids),
                "documents_by_status": docs_by_status,
            },
        }

    @staticmethod
    def _resolve_sources_type(sources: List[dict]) -> str:
        if not sources:
            return "none"

        source_types = {
            str(item.get("source_type") or "").strip().lower()
            for item in sources
            if str(item.get("source_type") or "").strip()
        }
        if not source_types:
            return "document_retrieval"
        if source_types.issubset({"retrieval"}):
            return "document_retrieval"
        return "tool_results"

    @staticmethod
    def _filter_sources_by_mode_quality(
        sources: List[dict], mode_enum: ModeType
    ) -> List[dict]:
        if not sources:
            return []
        if mode_enum != ModeType.ASK:
            return sources

        scored_values: List[float] = []
        scored_items: List[tuple[dict, float]] = []
        for src in sources:
            try:
                score = float(src.get("score", 0.0) or 0.0)
            except Exception:
                score = 0.0
            scored_items.append((src, score))
            scored_values.append(score)

        # Some retrievers/mode paths may omit scores or report 0.0 while still
        # returning valid source nodes. In that case, do not drop all citations.
        if not any(score > 0 for score in scored_values):
            return sources

        filtered: List[dict] = []
        for src, score in scored_items:
            if score >= ASK_SOURCE_SCORE_THRESHOLD:
                filtered.append(src)
        return filtered

    @staticmethod
    def _restore_ask_display_sources_if_empty(
        sources: List[dict],
        prevalidated_sources: List[dict],
        mode_enum: ModeType,
    ) -> List[dict]:
        if sources or mode_enum != ModeType.ASK or not prevalidated_sources:
            return sources

        # Display-only fallback: keep retrieval snippets for UI even if document_id
        # validation failed or all scores fell below threshold. Reference persistence
        # still skips invalid IDs. Do NOT re-apply score filtering here — the whole
        # point of this fallback is to show something when quality filtering left nothing.
        restored: List[dict] = []
        for src in prevalidated_sources:
            title = str(src.get("title", "") or "")
            text = str(src.get("text", "") or "")
            if not title and not text:
                continue
            restored.append(
                {
                    "document_id": str(src.get("document_id", "") or ""),
                    "chunk_id": str(src.get("chunk_id", "") or ""),
                    "title": title,
                    "text": text,
                    "score": src.get("score", 0.0),
                }
            )
        return restored

    async def _get_notebook_scope(
        self, notebook_id: str
    ) -> tuple[List[str], Dict[str, int], List[str], Dict[str, str]]:
        """Collect retrieval scope and processing status overview for notebook refs."""
        zero_counts = {status.value: 0 for status in DocumentStatus}
        refs = await self._ref_repo.list_by_notebook(notebook_id)
        if not refs:
            return [], zero_counts, [], {}

        docs = await self._document_repo.get_batch([ref.document_id for ref in refs])
        completed_doc_ids = list(
            {doc.document_id for doc in docs if doc.status == DocumentStatus.COMPLETED}
        )
        completed_doc_titles = {
            doc.document_id: getattr(doc, "title", "")
            for doc in docs
            if doc.status == DocumentStatus.COMPLETED and getattr(doc, "title", "")
        }
        counts = {status.value: 0 for status in DocumentStatus}
        blocking_ids: List[str] = []
        blocking_statuses = {
            DocumentStatus.UPLOADED,
            DocumentStatus.PENDING,
            DocumentStatus.PROCESSING,
            DocumentStatus.CONVERTED,
        }
        for doc in docs:
            counts[doc.status.value] = counts.get(doc.status.value, 0) + 1
            if doc.status in blocking_statuses:
                blocking_ids.append(doc.document_id)

        return completed_doc_ids, counts, blocking_ids, completed_doc_titles

    @staticmethod
    def _build_mode_context(
        context: Optional[dict],
        completed_doc_titles: Dict[str, str],
    ) -> Optional[dict]:
        """Attach notebook title hints for retrieval fallback without changing API schema."""
        if not completed_doc_titles:
            return context
        titles = [title for title in completed_doc_titles.values() if title]
        if not titles:
            return context

        merged = dict(context or {})
        existing_titles = merged.get("allowed_document_titles")
        if isinstance(existing_titles, list):
            return merged
        merged["allowed_document_titles"] = titles
        return merged

    async def _get_context_chunks(self, context: dict) -> List[dict]:
        """Fetch chunk and neighbors by chunk_id for richer context.

        If only selected_text is provided, return it as a pseudo chunk to ensure
        it appears in sources even when not yet indexed.
        """
        if not context:
            return []

        if context.get("selected_text") and not context.get("chunk_id"):
            return [
                {
                    "document_id": context.get("document_id"),
                    "chunk_id": "user_selection",
                    "text": context.get("selected_text"),
                    "title": "",
                    "score": 1.0,
                }
            ]

        if not context.get("chunk_id"):
            return []

        try:
            vector_index = await self._get_vector_index()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Skipping context chunk retrieval because vector index is unavailable: %s",
                exc,
            )
            return []

        if not vector_index:
            return []

        doc_id = context.get("document_id")
        chunk_idx = context.get("chunk_index")
        filters = []
        from llama_index.core.vector_stores import (
            MetadataFilters,
            MetadataFilter,
            FilterOperator,
        )

        metadata_filters = None
        if doc_id:
            filters.append(
                MetadataFilter(
                    key="document_id",
                    value=doc_id,
                    operator=FilterOperator.EQ,
                )
            )
        if chunk_idx is not None:
            try:
                idx = int(chunk_idx)
                filters.append(
                    MetadataFilter(
                        key="chunk_index",
                        value=[idx - 1, idx, idx + 1],
                        operator=FilterOperator.IN,
                    )
                )
            except Exception:
                pass
        if filters:
            metadata_filters = MetadataFilters(filters=filters)

        retriever = vector_index.as_retriever(
            similarity_top_k=5,
            filters=metadata_filters,
        )
        try:
            results = retriever.retrieve(context.get("selected_text", ""))
        except Exception:
            return []
        chunks = []
        for node in results:
            meta = getattr(node.node, "metadata", {}) if hasattr(node, "node") else {}
            doc_id = extract_document_id(node)
            chunks.append(
                {
                    "document_id": doc_id,
                    "chunk_id": getattr(node.node, "node_id", ""),
                    "text": node.node.get_content() if hasattr(node, "node") else "",
                    "title": meta.get("title", ""),
                    "score": getattr(node, "score", 0.0),
                }
            )
        return chunks

    @staticmethod
    def _merge_sources_with_context(
        sources: List[dict], context: Optional[dict], context_chunks: List[dict]
    ) -> List[dict]:
        """Ensure user selection appears first, followed by context chunks and retriever sources."""

        merged: List[dict] = []

        def _add(src: dict):
            key = (src.get("document_id"), src.get("chunk_id"), src.get("text"))
            if key not in {
                (m.get("document_id"), m.get("chunk_id"), m.get("text")) for m in merged
            }:
                merged.append(src)

        if context and context.get("document_id") and context.get("selected_text"):
            _add(
                {
                    "document_id": context.get("document_id"),
                    "chunk_id": context.get("chunk_id", "user_selection"),
                    "text": context.get("selected_text"),
                    "title": "",
                    "score": 1.0,
                }
            )

        for c in context_chunks or []:
            _add(c)

        for s in sources or []:
            _add(s)

        return merged

    async def _filter_valid_sources(self, sources: List[dict]) -> List[dict]:
        """Ensure document_id exists before persisting references."""
        if not sources:
            return []

        cache = {}
        valid = []
        missing_counts: Dict[str, int] = {}
        for src in sources:
            doc_id = src.get("document_id")
            if not doc_id:
                continue
            if doc_id not in cache:
                cache[doc_id] = bool(await self._document_repo.get(doc_id))
            if not cache[doc_id]:
                missing_counts[doc_id] = missing_counts.get(doc_id, 0) + 1
                continue
            valid.append(src)

        for doc_id, count in missing_counts.items():
            logger.warning(
                "Skipping %s source item(s) with missing document_id: %s",
                count,
                doc_id,
            )
        return valid
