"""Session management for MediMind Agent.

This version stores sessions/messages in the business tables (sessions, messages)
and scopes retrieval to the current notebook.
"""

from typing import Optional, List, AsyncGenerator
from datetime import datetime

from llama_index.core.llms import LLM
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core import VectorStoreIndex

from medimind_agent.core.engine.modes.base import ModeType
from medimind_agent.core.engine.selector import ModeSelector
from medimind_agent.domain.entities.session import Session
from medimind_agent.domain.entities.message import Message
from medimind_agent.domain.repositories.session_repository import SessionRepository
from medimind_agent.domain.repositories.message_repository import MessageRepository
from medimind_agent.domain.value_objects.mode_type import MessageRole
from medimind_agent.core.common.config import get_memory_token_limit


class SessionManager:
    """Manages conversation sessions with mode support."""

    def __init__(
        self,
        llm: LLM,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
        pgvector_index: Optional[VectorStoreIndex] = None,
        es_index: Optional[VectorStoreIndex] = None,
        es_index_name: str = "medimind_docs",
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
        self._conclude_memory = ChatMemoryBuffer.from_defaults(
            token_limit=self._memory_token_limit,
            llm=llm,
        )

        self._mode_selector = ModeSelector(
            llm=llm,
            pgvector_index=pgvector_index,
            es_index=es_index,
            memory=self._memory,
            es_index_name=es_index_name,
            conclude_memory=self._conclude_memory,
        )

        self._current_session: Optional[Session] = None
        self._current_mode: ModeType = ModeType.CHAT

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
        messages = await self._message_repo.list_by_session(
            self._current_session.session_id,
            limit=50,
        )
        self._memory.reset()
        from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole as LlamaMessageRole

        for msg in messages:
            role = LlamaMessageRole.USER if msg.role == MessageRole.USER else LlamaMessageRole.ASSISTANT
            self._memory.put(LlamaChatMessage(role=role, content=msg.content))

    def switch_mode(self, mode_type: ModeType) -> None:
        self._current_mode = mode_type

    async def chat(
        self,
        message: str,
        mode_type: Optional[ModeType] = None,
        allowed_document_ids: Optional[List[str]] = None,
        context: Optional[dict] = None,
    ) -> tuple:
        if not self._current_session:
            raise ValueError("Session not started")

        effective_mode = mode_type or self._current_mode
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
        self._conclude_memory.reset()

    def get_status(self) -> dict:
        return {
            "session_id": self.session_id,
            "current_mode": self._current_mode.value,
            "mode_info": self._mode_selector.get_mode_info(self._current_mode),
            "has_persistence": True,
            "memory_messages": len(self._memory.get_all()) if self._memory else 0,
        }
