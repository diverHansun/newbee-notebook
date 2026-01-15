"""Session management for MediMind Agent.

This module integrates mode selection with session persistence,
allowing conversation history to be stored and retrieved across sessions.
"""

import uuid
from typing import Optional, List
from datetime import datetime

from llama_index.core.llms import LLM
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core import VectorStoreIndex

from src.engine.modes.base import ModeType
from src.engine.selector import ModeSelector
from src.infrastructure.session import (
    ChatSessionStore,
    ChatSession,
    ChatMessage,
    ModeType as SessionModeType,
    MessageRole,
)


class SessionManager:
    """Manages conversation sessions with mode support.
    
    This class provides:
    - Session creation and management
    - Message persistence to PostgreSQL
    - Mode switching within a session
    - Conversation history loading
    
    Attributes:
        session_store: PostgreSQL session storage
        mode_selector: Mode factory and manager
        current_session: Active session
    """
    
    def __init__(
        self,
        llm: LLM,
        session_store: Optional[ChatSessionStore] = None,
        pgvector_index: Optional[VectorStoreIndex] = None,
        es_index: Optional[VectorStoreIndex] = None,
        es_index_name: str = "medimind_docs",
        memory_token_limit: int = 3000,
    ):
        """Initialize SessionManager.
        
        Args:
            llm: LLM instance
            session_store: PostgreSQL session store (optional)
            pgvector_index: pgvector-backed index
            es_index: Elasticsearch-backed index
            es_index_name: ES index name for Chat mode tool
            memory_token_limit: Token limit for conversation memory
        """
        self._llm = llm
        self._session_store = session_store
        self._memory_token_limit = memory_token_limit
        
        # Create shared memory for agent-based modes (chat, ask)
        self._memory = ChatMemoryBuffer.from_defaults(
            token_limit=memory_token_limit,
            llm=llm,
        )
        # Separate memory for conclude mode (to avoid mixing with chat/ask)
        self._conclude_memory = ChatMemoryBuffer.from_defaults(
            token_limit=memory_token_limit,
            llm=llm,
        )
        
        # Create mode selector
        self._mode_selector = ModeSelector(
            llm=llm,
            pgvector_index=pgvector_index,
            es_index=es_index,
            memory=self._memory,
            es_index_name=es_index_name,
            conclude_memory=self._conclude_memory,
        )
        
        self._current_session: Optional[ChatSession] = None
        self._current_mode: ModeType = ModeType.CHAT
    
    @property
    def session_id(self) -> Optional[str]:
        """Get current session ID."""
        if self._current_session:
            return str(self._current_session.session_id)
        return None

    @property
    def session_store(self) -> Optional[ChatSessionStore]:
        """Expose session store if configured."""
        return self._session_store
    
    @property
    def current_mode(self) -> ModeType:
        """Get current interaction mode."""
        return self._current_mode
    
    @property
    def mode_selector(self) -> ModeSelector:
        """Get the mode selector."""
        return self._mode_selector
    
    async def start_session(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> ChatSession:
        """Start a new session or resume an existing one.
        
        Args:
            session_id: Optional session ID to resume
            metadata: Optional session metadata
            
        Returns:
            ChatSession instance
        """
        if session_id and self._session_store:
            # Try to resume existing session
            session = await self._session_store.get_session(session_id)
            if session:
                self._current_session = session
                # Load history into memory
                await self._load_session_history()
                return session
        
        # Create new session
        if self._session_store:
            self._current_session = await self._session_store.create_session()
        else:
            # Create local session without persistence
            self._current_session = ChatSession()
        
        return self._current_session
    
    async def _load_session_history(self) -> None:
        """Load session history into memory."""
        if not self._session_store or not self._current_session:
            return
        
        messages = await self._session_store.get_messages(
            self._current_session.session_id,
            limit=50,  # Load last 50 messages
            descending=True,
        )
        
        # Clear current memory
        self._memory.reset()
        
        # Add messages to memory
        from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole as LlamaMessageRole
        
        for msg in messages:
            role = LlamaMessageRole.USER if msg.role == MessageRole.USER else LlamaMessageRole.ASSISTANT
            self._memory.put(LlamaChatMessage(role=role, content=msg.content))
    
    def switch_mode(self, mode_type: ModeType) -> None:
        """Switch to a different interaction mode.
        
        Args:
            mode_type: Mode to switch to
        """
        self._current_mode = mode_type
    
    async def chat(
        self,
        message: str,
        mode_type: Optional[ModeType] = None,
    ) -> str:
        """Process a chat message.
        
        Args:
            message: User message
            mode_type: Optional mode override (uses current mode if not specified)
            
        Returns:
            Assistant response
        """
        # Use specified mode or current mode
        effective_mode = mode_type or self._current_mode
        
        # Get response from mode
        response = await self._mode_selector.run(message, effective_mode)
        
        # Persist to session store if available
        if self._session_store and self._current_session:
            # Import ChatMessage from infrastructure.session
            from src.infrastructure.session import ChatMessage as SessionChatMessage
            
            # Get mode value (handle both enum and string)
            mode_value = effective_mode.value if hasattr(effective_mode, 'value') else str(effective_mode)
            
            # Save user message
            user_msg = SessionChatMessage(
                session_id=self._current_session.session_id,
                mode=SessionModeType(mode_value),
                role=MessageRole.USER,
                content=message,
            )
            await self._session_store.add_message(user_msg)
            
            # Save assistant response
            assistant_msg = SessionChatMessage(
                session_id=self._current_session.session_id,
                mode=SessionModeType(mode_value),
                role=MessageRole.ASSISTANT,
                content=response,
            )
            await self._session_store.add_message(assistant_msg)
        
        return response
    
    def chat_sync(
        self,
        message: str,
        mode_type: Optional[ModeType] = None,
    ) -> str:
        """Synchronous version of chat()."""
        import asyncio
        return asyncio.run(self.chat(message, mode_type))
    
    async def reset(self) -> None:
        """Reset conversation memory."""
        self._memory.reset()
        await self._mode_selector.reset_memory()
    
    async def get_history(self, limit: int = 50) -> List[ChatMessage]:
        """Get conversation history.
        
        Args:
            limit: Maximum number of messages to return
            
        Returns:
            List of chat messages
        """
        if self._session_store and self._current_session:
            return await self._session_store.get_messages(
                self._current_session.session_id,
                limit=limit,
                descending=True,
            )
        # Fallback to in-memory history (non-persisted)
        if self._memory:
            return self._memory.get_all()[-limit:]
        return []
    
    async def end_session(self) -> None:
        """End the current session."""
        self._current_session = None
        self._memory.reset()
        self._conclude_memory.reset()
    
    def get_status(self) -> dict:
        """Get current session status.
        
        Returns:
            Dictionary with session information
        """
        return {
            "session_id": self.session_id,
            "current_mode": self._current_mode.value,
            "mode_info": self._mode_selector.get_mode_info(self._current_mode),
            "has_persistence": self._session_store is not None,
            "memory_messages": len(self._memory.get_all()) if self._memory else 0,
        }
