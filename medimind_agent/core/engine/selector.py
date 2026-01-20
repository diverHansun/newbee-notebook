"""Mode selector for managing interaction modes.

This module provides the ModeSelector class that handles:
- Mode creation and caching
- Mode switching within a session
- Integration with session storage
"""

from typing import Optional, Dict, AsyncGenerator
from enum import Enum
from llama_index.core.llms import LLM
from llama_index.core.memory import BaseMemory, ChatMemoryBuffer
from llama_index.core import VectorStoreIndex

from medimind_agent.core.engine.modes.base import BaseMode, ModeType
from medimind_agent.core.engine.modes.chat_mode import ChatMode
from medimind_agent.core.engine.modes.ask_mode import AskMode
from medimind_agent.core.engine.modes.conclude_mode import ConcludeMode
from medimind_agent.core.engine.modes.explain_mode import ExplainMode


class ModeSelector:
    """Mode selector for creating and managing interaction modes.
    
    This class provides:
    - Factory method for creating modes
    - Mode caching for reuse within a session
    - Shared memory across memory-enabled modes
    
    Attributes:
        llm: Language model instance
        pgvector_index: Optional pgvector-backed index
        es_index: Optional Elasticsearch-backed index
        memory: Shared conversation memory
    """
    
    def __init__(
        self,
        llm: LLM,
        pgvector_index: Optional[VectorStoreIndex] = None,
        es_index: Optional[VectorStoreIndex] = None,
        memory: Optional[BaseMemory] = None,
        es_index_name: str = "medimind_docs",
        conclude_memory: Optional[BaseMemory] = None,
    ):
        """Initialize ModeSelector.
        
        Args:
            llm: LLM instance for all modes
            pgvector_index: pgvector-backed index for RAG modes
            es_index: Elasticsearch-backed index for Ask mode
            memory: Shared conversation memory
            es_index_name: Elasticsearch index name for Chat mode tool
        """
        self._llm = llm
        self._pgvector_index = pgvector_index
        self._es_index = es_index
        self._memory = memory
        self._conclude_memory = conclude_memory or memory
        self._es_index_name = es_index_name
        
        # Mode cache
        self._modes: Dict[ModeType, BaseMode] = {}
        self._current_mode: Optional[ModeType] = None
    
    @property
    def current_mode(self) -> Optional[ModeType]:
        """Get the current active mode type."""
        return self._current_mode
    
    @property
    def available_modes(self) -> list:
        """Get list of available mode types."""
        return list(ModeType)
    
    def get_last_sources(self) -> list:
        """Get sources from the last mode run."""
        if self._current_mode and self._current_mode in self._modes:
            return self._modes[self._current_mode].last_sources
        return []
    
    def get_mode(self, mode_type: ModeType) -> BaseMode:
        """Get or create a mode by type.
        
        Modes are cached after first creation for reuse.
        
        Args:
            mode_type: Type of mode to get
            
        Returns:
            Mode instance
            
        Raises:
            ValueError: If mode requirements are not met
        """
        # Return cached mode if exists
        if mode_type in self._modes:
            self._current_mode = mode_type
            return self._modes[mode_type]
        
        # Create new mode
        mode = self._create_mode(mode_type)
        self._modes[mode_type] = mode
        self._current_mode = mode_type
        
        return mode
    
    def _create_mode(self, mode_type: ModeType) -> BaseMode:
        """Create a new mode instance.
        
        Args:
            mode_type: Type of mode to create
            
        Returns:
            New mode instance
        """
        if mode_type == ModeType.CHAT:
            return ChatMode(
                llm=self._llm,
                memory=self._memory,
                es_index_name=self._es_index_name,
                vector_index=self._pgvector_index,
            )
        
        elif mode_type == ModeType.ASK:
            return AskMode(
                llm=self._llm,
                pgvector_index=self._pgvector_index,
                es_index=self._es_index,
                memory=self._memory,
            )
        
        elif mode_type == ModeType.CONCLUDE:
            if self._pgvector_index is None:
                raise ValueError("Conclude mode requires pgvector index")
            return ConcludeMode(
                llm=self._llm,
                index=self._pgvector_index,
                memory=self._conclude_memory,
            )
        
        elif mode_type == ModeType.EXPLAIN:
            if self._pgvector_index is None:
                raise ValueError("Explain mode requires pgvector index")
            return ExplainMode(
                llm=self._llm,
                index=self._pgvector_index,
            )
        
        else:
            raise ValueError(f"Unknown mode type: {mode_type}")
    
    async def run(
        self,
        message: str,
        mode_type: ModeType,
        allowed_document_ids: Optional[list] = None,
        context: Optional[dict] = None,
    ) -> str:
        """Run a message through a specific mode.
        
        Args:
            message: User message
            mode_type: Mode to use
            
        Returns:
            Response from the mode
        """
        mode = self.get_mode(mode_type)
        mode.set_allowed_documents(allowed_document_ids)
        mode.set_context(context)
        return await mode.run(message)

    async def run_stream(
        self,
        message: str,
        mode_type: ModeType,
        allowed_document_ids: Optional[list] = None,
        context: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a response through a specific mode.

        Args:
            message: User message
            mode_type: Mode to use
            allowed_document_ids: Optional document scope filter
            context: Optional context (e.g., selected text)

        Yields:
            Response text chunks from the mode
        """
        mode = self.get_mode(mode_type)
        mode.set_allowed_documents(allowed_document_ids)
        mode.set_context(context)
        async for chunk in mode.stream(message):
            yield chunk

    def run_sync(
        self,
        message: str,
        mode_type: ModeType,
        allowed_document_ids: Optional[list] = None,
    ) -> str:
        """Synchronous version of run().
        
        Args:
            message: User message
            mode_type: Mode to use
            
        Returns:
            Response from the mode
        """
        import asyncio
        return asyncio.run(self.run(message, mode_type, allowed_document_ids))
    
    async def reset_memory(self) -> None:
        """Reset the shared conversation memory."""
        if self._memory is not None:
            self._memory.reset()
        
        # Also reset individual mode memories
        for mode in self._modes.values():
            await mode.reset()
    
    def get_mode_info(self, mode_type: ModeType) -> dict:
        """Get information about a mode.
        
        Args:
            mode_type: Mode type to get info for
            
        Returns:
            Dictionary with mode information
        """
        info = {
            ModeType.CHAT: {
                "name": "Chat",
                "description": "Free-form conversation with web search and knowledge base access",
                "has_memory": True,
                "has_rag": False,
            },
            ModeType.ASK: {
                "name": "Ask",
                "description": "Deep Q&A with RAG and hybrid retrieval",
                "has_memory": True,
                "has_rag": True,
            },
            ModeType.CONCLUDE: {
                "name": "Conclude",
                "description": "Document summarization and conclusion generation",
                "has_memory": False,
                "has_rag": True,
            },
            ModeType.EXPLAIN: {
                "name": "Explain",
                "description": "Concept explanation and knowledge clarification",
                "has_memory": False,
                "has_rag": True,
            },
        }
        return info.get(mode_type, {})


def parse_mode_from_input(user_input: str) -> tuple:
    """Parse mode switch command from user input.
    
    Supports formats:
    - /mode chat
    - /chat
    - @chat message
    
    Args:
        user_input: Raw user input
        
    Returns:
        Tuple of (mode_type or None, cleaned message)
    """
    user_input = user_input.strip()
    
    # Check /mode command
    if user_input.lower().startswith("/mode "):
        mode_name = user_input[6:].strip().lower()
        try:
            return ModeType(mode_name), ""
        except ValueError:
            return None, user_input
    
    # Check shorthand commands
    for mode_type in ModeType:
        if user_input.lower().startswith(f"/{mode_type.value}"):
            remaining = user_input[len(mode_type.value) + 1:].strip()
            return mode_type, remaining
        
        if user_input.lower().startswith(f"@{mode_type.value} "):
            remaining = user_input[len(mode_type.value) + 2:].strip()
            return mode_type, remaining
    
    return None, user_input


def get_mode_help() -> str:
    """Get help text for mode commands.
    
    Returns:
        Formatted help string
    """
    return """
Available modes:
  /mode chat     - Free conversation with tools (web/news/crawl/ES)
  /mode ask      - Deep Q&A with RAG (pgvector + Elasticsearch)
  /mode conclude - Summarize and draw conclusions from documents
  /mode explain  - Explain concepts from the knowledge base

Shortcuts:
  /chat, /ask, /conclude, /explain - Switch to a mode
  @chat <msg>, @ask <msg>          - Send message to specific mode

Current session commands:
  /status              - Show current mode and session info
  /history [n]         - Show last n messages (default 20)
  /session list        - List recent sessions (requires persistence)
  /resume <session_id> - Switch to an existing session
  /delete <session_id> - Delete a session (requires persistence)
  /new                 - Start a new conversation (close current session)
  /reset               - Reset in-memory history (does not delete DB)
  /help                - Show this help
  /quit                - Exit the application
"""


