"""QueryEngine building utilities for LlamaIndex.

This module provides functions to build query engines from VectorStoreIndex
with configurable parameters like top-k, postprocessors, and LLM integration.
"""

from typing import Optional, List, Any
from llama_index.core import VectorStoreIndex
from llama_index.core.llms import LLM
from llama_index.core.base.base_query_engine import BaseQueryEngine
from llama_index.core.postprocessor import SimilarityPostprocessor


def build_query_engine(
    index: VectorStoreIndex, 
    llm: Optional[LLM] = None,
    top_k: int = 5,
    similarity_cutoff: Optional[float] = None,
    postprocessors: Optional[List[Any]] = None,
    response_mode: str = "compact",
    streaming: bool = False,
    **kwargs: Any
) -> BaseQueryEngine:
    """Build a query engine from a VectorStoreIndex.
    
    Args:
        index: The vector store index to build the query engine from
        llm: Optional LLM to use for response generation (if None, uses index's default)
        top_k: Number of top similar nodes to retrieve (default: 5)
        similarity_cutoff: Minimum similarity score threshold (0-1)
        postprocessors: List of postprocessors to apply to retrieved nodes
        response_mode: Response synthesis mode:
            - "compact": Concatenate chunks and generate single response
            - "tree_summarize": Build tree of summaries
            - "simple_summarize": Simple concatenation
        streaming: Enable streaming responses
        **kwargs: Additional arguments to pass to the query engine
        
    Returns:
        BaseQueryEngine: The configured query engine
        
    Example:
        >>> from src.engine import load_pgvector_index_sync
        >>> from src.llm.zhipu import build_llm
        >>> from src.rag.embeddings import build_embedding
        >>> 
        >>> embed_model = build_embedding()
        >>> index = load_pgvector_index_sync(embed_model)
        >>> llm = build_llm()
        >>> query_engine = build_query_engine(
        ...     index, 
        ...     llm=llm, 
        ...     top_k=5,
        ...     similarity_cutoff=0.25
        ... )
        >>> response = query_engine.query("What is diabetes?")
    """
    # Prepare postprocessors list
    if postprocessors is None:
        postprocessors = []
        
    # Add similarity postprocessor if cutoff is specified
    if similarity_cutoff is not None:
        postprocessors.append(
            SimilarityPostprocessor(similarity_cutoff=similarity_cutoff)
        )
    
    # Build query engine with specified parameters
    query_engine = index.as_query_engine(
        llm=llm,
        similarity_top_k=top_k,
        node_postprocessors=postprocessors,
        response_mode=response_mode,
        streaming=streaming,
        **kwargs
    )
    
    return query_engine


def build_simple_query_engine(
    index: VectorStoreIndex,
    llm: Optional[LLM] = None,
    top_k: int = 5
) -> BaseQueryEngine:
    """Build a simple query engine with minimal configuration.
    
    This is a convenience function for quick setup without advanced features.
    
    Args:
        index: The vector store index to build the query engine from
        llm: Optional LLM to use for response generation
        top_k: Number of top similar nodes to retrieve (default: 5)
        
    Returns:
        BaseQueryEngine: The configured query engine
        
    Example:
        >>> from src.engine import load_pgvector_index_sync
        >>> from src.rag.embeddings import build_embedding
        >>> 
        >>> embed_model = build_embedding()
        >>> index = load_pgvector_index_sync(embed_model)
        >>> query_engine = build_simple_query_engine(index, top_k=5)
    """
    return index.as_query_engine(
        llm=llm,
        similarity_top_k=top_k
    )





