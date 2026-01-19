"""
MediMind Agent - Chat Service

Application service for chat operations.
"""

from typing import Optional, List, AsyncGenerator, Dict, Any
import logging
from dataclasses import dataclass

from medimind_agent.domain.entities.session import Session
from medimind_agent.domain.value_objects.mode_type import ModeType
from medimind_agent.domain.repositories.session_repository import SessionRepository
from medimind_agent.domain.repositories.notebook_repository import NotebookRepository
from medimind_agent.domain.repositories.reference_repository import ReferenceRepository
from medimind_agent.domain.entities.reference import Reference
from medimind_agent.core.engine import SessionManager


logger = logging.getLogger(__name__)


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
        session_manager: SessionManager,
    ):
        self._session_repo = session_repo
        self._notebook_repo = notebook_repo
        self._reference_repo = reference_repo
        self._session_manager = session_manager
    
    async def chat(
        self,
        session_id: str,
        message: str,
        mode: str = "chat",
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

        # Generate response via SessionManager + ModeSelector
        response_content, sources = await self._session_manager.chat(
            message=message,
            mode_type=mode_enum,
        )
        message_id = session.message_count + 1
        
        # Update session message count
        await self._session_repo.increment_message_count(session_id, 2)  # +2 for user and assistant

        # Persist references if any
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
            await self._reference_repo.create_batch(refs)

        return ChatResult(
            session_id=session_id,
            message_id=message_id,
            content=response_content,
            mode=mode_enum,
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
        )
    
    async def chat_stream(
        self,
        session_id: str,
        message: str,
        mode: str = "chat",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send a message and stream the response.
        
        Args:
            session_id: Session ID.
            message: User message.
            mode: Chat mode.
            
        Yields:
            Event dictionaries with type and data.
        """
        # Get session
        session = await self._session_repo.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        mode_enum = ModeType(mode)
        message_id = session.message_count + 1
        
        # Yield start event
        yield {
            "type": "start",
            "message_id": message_id,
        }
        
        # TODO: Integrate with actual streaming LLM
        # For now, simulate streaming
        response_content = f"Placeholder streaming response to: {message}"
        
        for word in response_content.split():
            yield {
                "type": "content",
                "delta": word + " ",
            }
        
        # Yield sources
        yield {
            "type": "sources",
            "sources": [],
        }
        
        # Yield done
        yield {
            "type": "done",
        }

        # Update session message count
        await self._session_repo.increment_message_count(session_id, 2)


