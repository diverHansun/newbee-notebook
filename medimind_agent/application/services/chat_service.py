"""
MediMind Agent - Chat Service

Application service for chat operations.
"""

from typing import Optional, List, AsyncGenerator, Dict, Any
import asyncio
import logging
from dataclasses import dataclass

from medimind_agent.domain.entities.session import Session
from medimind_agent.domain.value_objects.mode_type import ModeType, MessageRole
from medimind_agent.domain.repositories.session_repository import SessionRepository
from medimind_agent.domain.repositories.notebook_repository import NotebookRepository
from medimind_agent.domain.repositories.reference_repository import (
    ReferenceRepository,
    NotebookDocumentRefRepository,
)
from medimind_agent.domain.repositories.document_repository import DocumentRepository
from medimind_agent.domain.repositories.message_repository import MessageRepository
from medimind_agent.domain.entities.reference import Reference
from medimind_agent.domain.entities.message import Message
from medimind_agent.domain.value_objects.document_status import DocumentStatus
from medimind_agent.core.engine import SessionManager
from medimind_agent.core.common.node_utils import extract_document_id


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
        document_repo: DocumentRepository,
        ref_repo: NotebookDocumentRefRepository,
        message_repo: MessageRepository,
        session_manager: SessionManager,
    ):
        self._session_repo = session_repo
        self._notebook_repo = notebook_repo
        self._reference_repo = reference_repo
        self._document_repo = document_repo
        self._ref_repo = ref_repo
        self._message_repo = message_repo
        self._session_manager = session_manager
        self._vector_index = session_manager.vector_index
    
    async def chat(
        self,
        session_id: str,
        message: str,
        mode: str = "chat",
        context: Optional[dict] = None,
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

        # Ensure session manager is aligned with this session (loads history)
        await self._session_manager.start_session(session_id=session_id)

        # Notebook scope documents
        allowed_doc_ids = await self._get_notebook_document_ids(session.notebook_id)
        await self._validate_mode_guard(mode_enum, allowed_doc_ids, context)

        # Fetch context-based chunks (used for sources/references)
        context_chunks = await self._get_context_chunks(context) if context else []

        # Generate response via SessionManager + ModeSelector
        response_content, sources = await self._session_manager.chat(
            message=message,
            mode_type=mode_enum,
            allowed_document_ids=allowed_doc_ids,
            context=context,
        )
        message_id = session.message_count + 1

        # Persist messages
        user_msg = Message(
            session_id=session_id,
            mode=mode_enum,
            role=MessageRole.USER,
            content=message,
        )
        assistant_msg = Message(
            session_id=session_id,
            mode=mode_enum,
            role=MessageRole.ASSISTANT,
            content=response_content,
        )
        await self._message_repo.create_batch([user_msg, assistant_msg])
        await self._session_repo.increment_message_count(session_id, 2)

        # Merge sources with user selection/context chunks for consistency
        sources = self._merge_sources_with_context(sources or [], context, context_chunks)
        sources = await self._filter_valid_sources(sources)

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
        context: Optional[dict] = None,
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
            - {"type": "content", "delta": str}
            - {"type": "sources", "sources": list}
            - {"type": "done"}
            - {"type": "error", "error_code": str, "message": str}
        """
        session = await self._session_repo.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        mode_enum = ModeType(mode)
        await self._session_manager.start_session(session_id=session_id)
        allowed_doc_ids = await self._get_notebook_document_ids(session.notebook_id)
        await self._validate_mode_guard(mode_enum, allowed_doc_ids, context)

        message_id = session.message_count + 1

        yield {"type": "start", "message_id": message_id}

        full_response = ""
        sources: List[dict] = []
        context_chunks = await self._get_context_chunks(context) if context else []

        try:
            stream = self._session_manager.chat_stream(
                message=message,
                mode_type=mode_enum,
                allowed_document_ids=allowed_doc_ids,
                context=context,
            )
            while True:
                try:
                    chunk = await asyncio.wait_for(stream.__anext__(), timeout=60)
                except StopAsyncIteration:
                    break
                full_response += chunk
                yield {"type": "content", "delta": chunk}

            sources = self._merge_sources_with_context(
                self._session_manager.get_last_sources(), context, context_chunks
            )
            sources = await self._filter_valid_sources(sources)

            yield {"type": "sources", "sources": sources or []}
            yield {"type": "done"}

            # Persist messages after successful streaming
            user_msg = Message(
                session_id=session_id,
                mode=mode_enum,
                role=MessageRole.USER,
                content=message,
            )
            assistant_msg = Message(
                session_id=session_id,
                mode=mode_enum,
                role=MessageRole.ASSISTANT,
                content=full_response,
            )
            await self._message_repo.create_batch([user_msg, assistant_msg])
            await self._session_repo.increment_message_count(session_id, 2)

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

        except asyncio.TimeoutError:
            yield {"type": "error", "error_code": "timeout", "message": "Stream timeout"}
        except asyncio.CancelledError:
            logger.info(f"Stream cancelled for session {session_id}")
            return
        except Exception as exc:
            logger.error(f"Stream error for session {session_id}: {exc}")
            yield {"type": "error", "error_code": "internal_error", "message": str(exc)}

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
        allowed_doc_ids = await self._get_notebook_document_ids(session.notebook_id)
        mode_enum = ModeType(mode)
        await self._validate_mode_guard(mode_enum, allowed_doc_ids, context)

    async def _validate_mode_guard(
        self,
        mode_enum: ModeType,
        allowed_doc_ids: List[str],
        context: Optional[dict],
    ) -> None:
        """Common guard for conclude/explain modes."""
        if mode_enum in (ModeType.CONCLUDE, ModeType.EXPLAIN):
            if not allowed_doc_ids and not (context and context.get("selected_text")):
                raise ValueError(
                    "Conclude/Explain mode requires at least one processed document "
                    "or a selected_text context."
                )
            if context and context.get("selected_text") and not context.get("document_id"):
                raise ValueError("selected_text requires a document_id to ensure traceable sources")
            if self._session_manager.vector_index is None:
                raise RuntimeError("Vector index is not available")

    async def _get_notebook_document_ids(self, notebook_id: str) -> List[str]:
        """Collect completed referenced document IDs for scope filtering."""
        refs = await self._ref_repo.list_by_notebook(notebook_id)
        if not refs:
            return []

        docs = await self._document_repo.get_batch([ref.document_id for ref in refs])
        return list(
            {
                doc.document_id
                for doc in docs
                if doc.status == DocumentStatus.COMPLETED
            }
        )

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

        if not context.get("chunk_id") or not self._vector_index:
            return []

        doc_id = context.get("document_id")
        chunk_idx = context.get("chunk_index")
        filters = []
        from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator
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

        retriever = self._vector_index.as_retriever(
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
        for src in sources:
            doc_id = src.get("document_id")
            if not doc_id:
                continue
            if doc_id not in cache:
                cache[doc_id] = bool(await self._document_repo.get(doc_id))
            if not cache[doc_id]:
                logger.warning("Skipping source with missing document_id: %s", doc_id)
                continue
            valid.append(src)
        return valid
