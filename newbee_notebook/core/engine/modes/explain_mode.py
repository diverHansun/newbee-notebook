"""Explain mode implementation using QueryEngine.

This mode provides concept explanation and knowledge clarification:
- QueryEngine for single-turn Q&A
- RAG for retrieving relevant documents
- Optimized for explanatory responses

No conversation memory - each query is independent.
"""

from typing import Optional
from llama_index.core.llms import LLM
from llama_index.core.memory import BaseMemory
from llama_index.core.base.base_query_engine import BaseQueryEngine
from llama_index.core import VectorStoreIndex
from llama_index.core.prompts import PromptTemplate
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator

from newbee_notebook.core.engine.modes.base import BaseMode, ModeConfig, ModeType
from newbee_notebook.core.prompts import load_prompt
from newbee_notebook.core.rag.retrieval import build_hybrid_retriever
from newbee_notebook.core.rag.retrieval.filters import build_document_filters
from newbee_notebook.core.common.node_utils import extract_document_id

DEFAULT_EXPLAIN_SYSTEM_PROMPT = load_prompt("explain.md")


EXPLAIN_QA_TEMPLATE = PromptTemplate(
    """You are an expert at explaining concepts clearly and thoroughly.

Context information from the knowledge base:
---------------------
{context_str}
---------------------

Based on the above context, please provide a clear and comprehensive explanation for the following question. 
If the context doesn't contain relevant information, use your knowledge but indicate this clearly.

Question: {query_str}

Explanation:"""
)


class ExplainMode(BaseMode):
    """Explain mode using QueryEngine for explanations.
    
    This mode provides:
    - Concept explanation and clarification
    - RAG for retrieving relevant reference material
    - Single-turn Q&A optimized for educational responses
    
    Note: This mode does NOT maintain conversation memory.
    Each query is treated as an independent explanation request.
    
    Attributes:
        _query_engine: QueryEngine instance for explanations
        _index: VectorStoreIndex for retrieval
    """
    
    def __init__(
        self,
        llm: LLM,
        index: Optional[VectorStoreIndex] = None,
        es_index: Optional[VectorStoreIndex] = None,
        memory: Optional[BaseMemory] = None,
        config: Optional[ModeConfig] = None,
        similarity_top_k: int = 5,
        response_mode: str = "compact",
    ):
        """Initialize ExplainMode.
        
        Args:
            llm: LLM instance
            index: VectorStoreIndex for document retrieval
            memory: Not used in this mode (always None)
            config: Mode configuration
            similarity_top_k: Number of documents to retrieve
            response_mode: Response synthesis mode
        """
        # Force memory to None for this mode
        super().__init__(llm=llm, memory=None, config=config)
        
        self._index = index
        self._es_index = es_index
        self._similarity_top_k = similarity_top_k
        self._response_mode = response_mode

        self._query_engine: Optional[BaseQueryEngine] = None
        self._retriever = None
    
    def _default_config(self) -> ModeConfig:
        """Return default Explain mode configuration."""
        return ModeConfig(
            mode_type=ModeType.EXPLAIN,
            has_memory=False,  # No memory for explain mode
            system_prompt=load_prompt("explain.md"),
            verbose=False,
        )
    
    async def _initialize(self) -> None:
        """Initialize the QueryEngine for explanations."""
        if self._index is None or self._es_index is None:
            raise ValueError("ExplainMode requires both pgvector and ES indexes")
        await self._refresh_engine()

    async def _refresh_engine(self) -> None:
        """Rebuild retriever/query engine when allowed scope changes."""
        pg_filters, es_filters, allowed_ids = build_document_filters(self.allowed_doc_ids, key="ref_doc_id")
        # Hybrid retriever: pgvector + ES
        self._retriever = build_hybrid_retriever(
            pgvector_index=self._index,
            es_index=self._es_index,
            pgvector_top_k=self._similarity_top_k,
            es_top_k=self._similarity_top_k,
            final_top_k=self._similarity_top_k,
            pg_filters=pg_filters,
            es_filters=es_filters,
            allowed_doc_ids=allowed_ids,
        )
        self._query_engine = RetrieverQueryEngine.from_args(
            retriever=self._retriever,
            llm=self._llm,
            response_mode=self._response_mode,
            text_qa_template=EXPLAIN_QA_TEMPLATE,
            verbose=self._config.verbose,
        )
    
    async def _process(self, message: str) -> str:
        """Process explanation request using QueryEngine.
        
        Args:
            message: User's question to explain
            
        Returns:
            Generated explanation
        """
        if self.scope_changed():
            await self._refresh_engine()

        query = self._build_enhanced_query(message)

        try:
            response = await self._query_engine.aquery(query)
        except AttributeError:
            response = self._query_engine.query(query)

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
        # Always include user selection as first source when present
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
        """Stream explanation if engine supports it."""
        if self.scope_changed():
            await self._refresh_engine()
        query = self._build_enhanced_query(message)
        try:
            if hasattr(self._query_engine, "astream_query"):
                async for chunk in self._query_engine.astream_query(query):
                    text = getattr(chunk, "response", None) or getattr(chunk, "text", None)
                    if text:
                        yield str(text)
                # refresh sources after stream
                response = await self._query_engine.aquery(query)
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
        # fallback non-stream
        yield await self._process(message)
    
    @property
    def query_engine(self) -> Optional[BaseQueryEngine]:
        """Get the QueryEngine instance."""
        return self._query_engine
    
    async def reset(self) -> None:
        """Reset is a no-op for ExplainMode (no memory)."""
        pass

    def _build_enhanced_query(self, message: str) -> str:
        """Combine selected_text with user question to focus retrieval and answer."""
        selection = self.get_selected_text()
        if not selection:
            return message

        return (
            "请基于以下选中的文本内容进行解释:\n\n"
            f"选中内容:\n---\n{selection}\n---\n\n"
            f"用户问题: {message}\n\n"
            "要求:\n1. 先解释选中文本的核心概念\n"
            "2. 结合知识库相关信息补充说明\n"
            "3. 专业术语给出通俗解释\n"
            "4. 保持回答简洁清晰"
        )


def build_explain_mode(
    llm: LLM,
    index: VectorStoreIndex,
    es_index: VectorStoreIndex,
    similarity_top_k: int = 5,
    response_mode: str = "compact",
) -> ExplainMode:
    """Build an ExplainMode instance.
    
    Convenience function for creating an ExplainMode with common settings.
    
    Args:
        llm: LLM instance
        index: VectorStoreIndex for retrieval
        es_index: Elasticsearch-backed index for keyword retrieval
        similarity_top_k: Number of documents to retrieve
        response_mode: Response synthesis mode
        
    Returns:
        Configured ExplainMode instance
    """
    return ExplainMode(
        llm=llm,
        index=index,
        es_index=es_index,
        similarity_top_k=similarity_top_k,
        response_mode=response_mode,
    )


