"""Conclude mode implementation using ChatEngine.

This mode provides document summarization and conclusion generation:
- ChatEngine with condense_plus_context mode
- RAG for retrieving relevant documents
- Optimized for summarization tasks

No conversation memory - each query is treated independently.
"""

from typing import Optional
from llama_index.core.llms import LLM
from llama_index.core.memory import BaseMemory
from llama_index.core.chat_engine.types import BaseChatEngine
from llama_index.core import VectorStoreIndex
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator
from medimind_agent.core.rag.retrieval.filters import build_document_filters
from medimind_agent.core.common.node_utils import extract_document_id

from medimind_agent.core.engine.modes.base import BaseMode, ModeConfig, ModeType
from medimind_agent.core.prompts import load_prompt


DEFAULT_CONTEXT_PROMPT = """Based on the following documents, provide a comprehensive summary or conclusion.

Documents:
{context_str}

Please analyze the above and provide your summary."""

DEFAULT_CONCLUDE_SYSTEM_PROMPT = load_prompt("conclude.md")


class ConcludeMode(BaseMode):
    """Conclude mode using ChatEngine for summarization.
    
    This mode provides:
    - Document summarization and conclusion generation
    - RAG for retrieving relevant documents
    - condense_plus_context mode for optimal summarization
    
    Note: This mode does NOT maintain conversation memory.
    Each query is treated as an independent summarization request.
    
    Attributes:
        _chat_engine: ChatEngine instance for summarization
        _index: VectorStoreIndex for retrieval
    """
    
    def __init__(
        self,
        llm: LLM,
        index: Optional[VectorStoreIndex] = None,
        memory: Optional[BaseMemory] = None,
        config: Optional[ModeConfig] = None,
        similarity_top_k: int = 10,
        response_mode: str = "tree_summarize",
    ):
        """Initialize ConcludeMode.
        
        Args:
            llm: LLM instance
            index: VectorStoreIndex for document retrieval
            memory: Conversation memory (optional, for multi-turn summaries)
            config: Mode configuration
            similarity_top_k: Number of documents to retrieve
            response_mode: Response synthesis mode (tree_summarize recommended)
        """
        super().__init__(llm=llm, memory=memory, config=config)
        
        self._index = index
        self._similarity_top_k = similarity_top_k
        self._response_mode = response_mode
        # Conclude mode is stateless; force memory to None regardless of input
        self._memory = None
        
        self._chat_engine: Optional[BaseChatEngine] = None
        self._retriever = None
        self._filters_cache = None
    
    def _default_config(self) -> ModeConfig:
        """Return default Conclude mode configuration."""
        return ModeConfig(
            mode_type=ModeType.CONCLUDE,
            has_memory=False,  # No memory for conclude mode
            system_prompt=load_prompt("conclude.md"),
            verbose=False,
        )
    
    async def _initialize(self) -> None:
        """Initialize the ChatEngine for summarization."""
        if self._index is None:
            raise ValueError("ConcludeMode requires an index for RAG")
        await self._refresh_engine()

    async def _refresh_engine(self) -> None:
        """Rebuild retriever/chat engine when allowed scope changes."""
        pg_filters, es_filters, _ = build_document_filters(self.allowed_doc_ids, key="ref_doc_id")
        # ConcludeMode 只用 pgvector 检索
        self._retriever = self._index.as_retriever(
            similarity_top_k=self._similarity_top_k,
            filters=pg_filters,
        )
        self._chat_engine = RetrieverQueryEngine.from_args(
            retriever=self._retriever,
            llm=self._llm,
            response_mode=self._response_mode,
            system_prompt=self._config.system_prompt or load_prompt("conclude.md"),
            text_qa_template=None,
            verbose=self._config.verbose,
        )

    def _build_enhanced_query(self, message: str) -> str:
        """Compose query using selected_text when available."""
        selection = self.get_selected_text()
        if not selection:
            return message

        return (
            "请对以下选中的文本内容进行总结:\n\n"
            f"选中内容:\n---\n{selection}\n---\n\n"
            f"用户要求: {message}\n\n"
            "要求:\n1. 提取核心观点\n2. 按逻辑顺序组织总结\n3. 内容较长则分点列出关键信息\n4. 如有上下文缺失可标注假设"
        )
    
    async def _process(self, message: str) -> str:
        """Process summarization request using ChatEngine."""
        current_scope = tuple(sorted(self.allowed_doc_ids)) if self.allowed_doc_ids else None
        if current_scope != self._filters_cache:
            await self._refresh_engine()
            self._filters_cache = current_scope
        if self.scope_changed():
            await self._refresh_engine()

        query = self._build_enhanced_query(message)

        try:
            response = await self._chat_engine.aquery(query)
        except AttributeError:
            response = self._chat_engine.query(query)
        
        sources = []
        source_nodes = getattr(response, "source_nodes", None)
        if source_nodes:
            for n in source_nodes:
                doc_id = extract_document_id(n)
                meta = getattr(n.node, "metadata", {})
                sources.append(
                    {
                        "document_id": doc_id,
                        "chunk_id": getattr(n.node, "node_id", ""),
                        "text": n.node.get_content(),
                        "score": getattr(n, "score", 0.0),
                    }
                )

        selection = self.get_selected_text()
        doc_id = self.get_context_document_id()
        if selection and doc_id:
            sources.insert(
                0,
                {
                    "document_id": doc_id,
                    "chunk_id": getattr(self._context, "chunk_id", None) or "user_selection",
                    "text": selection,
                    "score": 1.0,
                },
            )

        self._last_sources = sources
        return str(response)

    async def _stream(self, message: str):
        """Stream summarization if chat engine supports streaming."""
        if self.scope_changed():
            await self._refresh_engine()
        query = self._build_enhanced_query(message)
        try:
            if hasattr(self._chat_engine, "astream_query"):
                async for chunk in self._chat_engine.astream_query(query):
                    text = getattr(chunk, "response", None) or getattr(chunk, "text", None)
                    if text:
                        yield str(text)
                # refresh sources after stream
                response = await self._chat_engine.aquery(query)
                sources = []
                for sn in getattr(response, "source_nodes", []) or []:
                    doc_id = extract_document_id(sn)
                    sources.append(
                        {
                            "document_id": doc_id,
                            "chunk_id": getattr(sn.node, "node_id", ""),
                            "text": sn.node.get_content(),
                            "score": getattr(sn, "score", 0.0),
                        }
                    )
                selection = self.get_selected_text()
                doc_id = self.get_context_document_id()
                if selection and doc_id:
                    sources.insert(
                        0,
                        {
                            "document_id": doc_id,
                            "chunk_id": getattr(self._context, "chunk_id", None) or "user_selection",
                            "text": selection,
                            "score": 1.0,
                        },
                    )
                self._last_sources = sources
                return
        except Exception:
            pass
        yield await self._process(message)
    
    @property
    def chat_engine(self) -> Optional[BaseChatEngine]:
        """Get the ChatEngine instance."""
        return self._chat_engine
    
    async def reset(self) -> None:
        """Reset conversation memory if available."""
        if self._memory is not None:
            self._memory.reset()


def build_conclude_mode(
    llm: LLM,
    index: VectorStoreIndex,
    similarity_top_k: int = 10,
    response_mode: str = "tree_summarize",
) -> ConcludeMode:
    """Build a ConcludeMode instance.
    
    Convenience function for creating a ConcludeMode with common settings.
    
    Args:
        llm: LLM instance
        index: VectorStoreIndex for retrieval
        similarity_top_k: Number of documents to retrieve
        response_mode: Response synthesis mode
        
    Returns:
        Configured ConcludeMode instance
    """
    return ConcludeMode(
        llm=llm,
        index=index,
        similarity_top_k=similarity_top_k,
        response_mode=response_mode,
    )


