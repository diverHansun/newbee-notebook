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

from medimind_agent.core.engine.modes.base import BaseMode, ModeConfig, ModeType
from medimind_agent.core.prompts import load_prompt

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
        self._similarity_top_k = similarity_top_k
        self._response_mode = response_mode
        
        self._query_engine: Optional[BaseQueryEngine] = None
    
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
        if self._index is None:
            raise ValueError("ExplainMode requires an index for RAG")
        
        # Create query engine optimized for explanations
        self._query_engine = self._index.as_query_engine(
            llm=self._llm,
            similarity_top_k=self._similarity_top_k,
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
        # Use query method (async if available)
        try:
            response = await self._query_engine.aquery(message)
        except AttributeError:
            # Fallback to sync if async not available
            response = self._query_engine.query(message)
        
        sources = []
        source_nodes = getattr(response, "source_nodes", None)
        if source_nodes:
            for n in source_nodes:
                meta = getattr(n.node, "metadata", {})
                sources.append(
                    {
                        "document_id": meta.get("document_id"),
                        "chunk_id": getattr(n.node, "node_id", ""),
                        "text": n.node.get_content(),
                        "score": getattr(n, "score", 0.0),
                    }
                )
        self._last_sources = sources
        return str(response)
    
    @property
    def query_engine(self) -> Optional[BaseQueryEngine]:
        """Get the QueryEngine instance."""
        return self._query_engine
    
    async def reset(self) -> None:
        """Reset is a no-op for ExplainMode (no memory)."""
        pass


def build_explain_mode(
    llm: LLM,
    index: VectorStoreIndex,
    similarity_top_k: int = 5,
    response_mode: str = "compact",
) -> ExplainMode:
    """Build an ExplainMode instance.
    
    Convenience function for creating an ExplainMode with common settings.
    
    Args:
        llm: LLM instance
        index: VectorStoreIndex for retrieval
        similarity_top_k: Number of documents to retrieve
        response_mode: Response synthesis mode
        
    Returns:
        Configured ExplainMode instance
    """
    return ExplainMode(
        llm=llm,
        index=index,
        similarity_top_k=similarity_top_k,
        response_mode=response_mode,
    )


