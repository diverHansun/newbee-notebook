"""Session management for Newbee Notebook.

This version stores sessions/messages in the business tables (sessions, messages)
and scopes retrieval to the current notebook.
"""

from typing import Optional, List, AsyncGenerator
from datetime import datetime

from llama_index.core.llms import LLM
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core import VectorStoreIndex

from newbee_notebook.core.engine.modes.base import ModeType
from newbee_notebook.core.engine.selector import ModeSelector
from newbee_notebook.domain.entities.session import Session
from newbee_notebook.domain.entities.message import Message
from newbee_notebook.domain.repositories.session_repository import SessionRepository
from newbee_notebook.domain.repositories.message_repository import MessageRepository
from newbee_notebook.domain.value_objects.mode_type import MessageRole
from newbee_notebook.core.common.config import get_memory_token_limit


class SessionManager:
    """Manages conversation sessions with mode support."""

    EC_MEMORY_TOKEN_LIMIT = 2000

    def __init__(
        self,
        llm: LLM,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
        pgvector_index: Optional[VectorStoreIndex] = None,
        es_index: Optional[VectorStoreIndex] = None,
        es_index_name: str = "newbee_notebook_docs",
        memory_token_limit: Optional[int] = None,
    ):
        self._llm = llm
        self._session_repo = session_repo
        self._message_repo = message_repo
        self._memory_token_limit = memory_token_limit or get_memory_token_limit()

        self._memory = ChatMemoryBuffer.from_defaults(
            token_limit=self._memory_token_limit,
            llm=llm,
        )
        self._ec_memory = ChatMemoryBuffer.from_defaults(
            token_limit=self.EC_MEMORY_TOKEN_LIMIT,
            llm=llm,
        )

        self._mode_selector = ModeSelector(
            llm=llm,
            pgvector_index=pgvector_index,
            es_index=es_index,
            memory=self._memory,
            es_index_name=es_index_name,
            ec_memory=self._ec_memory,
        )

        self._current_session: Optional[Session] = None
        self._current_mode: ModeType = ModeType.CHAT
        self._ec_context_summary: str = ""

    @property
    def session_id(self) -> Optional[str]:
        if self._current_session:
            return self._current_session.session_id
        return None

    @property
    def current_mode(self) -> ModeType:
        return self._current_mode

    @property
    def mode_selector(self) -> ModeSelector:
        return self._mode_selector

    @property
    def vector_index(self) -> Optional[VectorStoreIndex]:
        """Expose pgvector index for auxiliary lookups."""
        return getattr(self._mode_selector, "_pgvector_index", None)

    async def start_session(
        self,
        session_id: Optional[str] = None,
        notebook_id: Optional[str] = None,
    ) -> Session:
        """Start or resume a session."""
        if session_id:
            session = await self._session_repo.get(session_id)
            if not session:
                raise ValueError(f"Session not found: {session_id}")
            self._current_session = session
        else:
            if not notebook_id:
                raise ValueError("notebook_id is required to create a session")
            session = Session(notebook_id=notebook_id)
            self._current_session = await self._session_repo.create(session)

        await self._load_session_history()
        return self._current_session

    async def _load_session_history(self) -> None:
        """Load persisted messages into memory for the active session."""
        if not self._current_session:
            return

        sid = self._current_session.session_id
        ca_messages = await self._message_repo.list_by_session(
            sid,
            limit=50,
            modes=[ModeType.CHAT, ModeType.ASK],
        )
        ec_messages = await self._message_repo.list_by_session(
            sid,
            limit=10,
            modes=[ModeType.EXPLAIN, ModeType.CONCLUDE],
        )

        self._memory.reset()
        self._ec_memory.reset()
        from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole as LlamaMessageRole

        for msg in ca_messages:
            role = LlamaMessageRole.USER if msg.role == MessageRole.USER else LlamaMessageRole.ASSISTANT
            self._memory.put(LlamaChatMessage(role=role, content=msg.content))

        for msg in ec_messages:
            role = LlamaMessageRole.USER if msg.role == MessageRole.USER else LlamaMessageRole.ASSISTANT
            self._ec_memory.put(LlamaChatMessage(role=role, content=msg.content))

        self._ec_context_summary = self._build_ec_context_summary(ec_messages)

    @staticmethod
    def _build_ec_context_summary(ec_messages: List[Message]) -> str:
        """Build a compact summary from recent explain/conclude interactions."""
        if not ec_messages:
            return ""

        recent_messages = ec_messages[-6:]
        lines = ["[Recent Explain/Conclude Context]"]
        for msg in recent_messages:
            role = "User" if msg.role == MessageRole.USER else "Assistant"
            mode = "Explain" if msg.mode == ModeType.EXPLAIN else "Conclude"
            content = (msg.content or "").strip()
            if len(content) > 200:
                content = content[:200] + "..."
            lines.append(f"[{mode}] {role}: {content}")
        return "\n".join(lines)

    def switch_mode(self, mode_type: ModeType) -> None:
        self._current_mode = mode_type

    async def chat(
        self,
        message: str,
        mode_type: Optional[ModeType] = None,
        allowed_document_ids: Optional[List[str]] = None,
        context: Optional[dict] = None,
        include_ec_context: bool = False,
    ) -> tuple:
        if not self._current_session:
            raise ValueError("Session not started")

        effective_mode = mode_type or self._current_mode
        if (
            include_ec_context
            and effective_mode in (ModeType.CHAT, ModeType.ASK)
            and self._ec_context_summary
        ):
            merged_context = dict(context or {})
            merged_context["ec_context_summary"] = self._ec_context_summary
            context = merged_context

        response = await self._mode_selector.run(
            message,
            effective_mode,
            allowed_document_ids=allowed_document_ids,
            context=context,
        )
        sources = self._mode_selector.get_last_sources()

        return response, sources

    async def chat_stream(
        self,
        message: str,
        mode_type: Optional[ModeType] = None,
        allowed_document_ids: Optional[List[str]] = None,
        context: Optional[dict] = None,
        include_ec_context: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Stream a chat response.

        Args:
            message: User message
            mode_type: Optional mode override
            allowed_document_ids: Document scope filter
            context: Optional context (e.g., selected text)

        Yields:
            Response text chunks
        """
        if not self._current_session:
            raise ValueError("Session not started")

        effective_mode = mode_type or self._current_mode
        if (
            include_ec_context
            and effective_mode in (ModeType.CHAT, ModeType.ASK)
            and self._ec_context_summary
        ):
            merged_context = dict(context or {})
            merged_context["ec_context_summary"] = self._ec_context_summary
            context = merged_context

        async for chunk in self._mode_selector.run_stream(
            message,
            effective_mode,
            allowed_document_ids=allowed_document_ids,
            context=context,
        ):
            yield chunk

    def get_last_sources(self) -> List[dict]:
        """Get sources from the last streaming response."""
        return self._mode_selector.get_last_sources()

    def chat_sync(
        self,
        message: str,
        mode_type: Optional[ModeType] = None,
        allowed_document_ids: Optional[List[str]] = None,
        context: Optional[dict] = None,
    ) -> str:
        import asyncio
        return asyncio.run(self.chat(message, mode_type, allowed_document_ids, context))

    async def reset(self) -> None:
        self._memory.reset()
        await self._mode_selector.reset_memory()

    async def get_history(self, limit: int = 50) -> List[Message]:
        if not self._current_session:
            return []
        return await self._message_repo.list_by_session(
            self._current_session.session_id,
            limit=limit,
        )

    async def end_session(self) -> None:
        self._current_session = None
        self._memory.reset()
        self._ec_memory.reset()
        self._ec_context_summary = ""

    def get_status(self) -> dict:
        return {
            "session_id": self.session_id,
            "current_mode": self._current_mode.value,
            "mode_info": self._mode_selector.get_mode_info(self._current_mode),
            "has_persistence": True,
            "memory_messages": len(self._memory.get_all()) if self._memory else 0,
            "ec_memory_messages": len(self._ec_memory.get_all()) if self._ec_memory else 0,
        }
