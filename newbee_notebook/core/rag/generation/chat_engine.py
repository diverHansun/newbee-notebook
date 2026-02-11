"""ChatEngine building utilities for multi-turn conversations with memory.

This module provides functions to build chat engines from VectorStoreIndex
with conversation memory management using ChatSummaryMemoryBuffer.
"""

from typing import Optional, List, Any
from llama_index.core import VectorStoreIndex
from llama_index.core.llms import LLM
from llama_index.core.chat_engine.types import BaseChatEngine
from llama_index.core.memory import ChatSummaryMemoryBuffer
from llama_index.core.postprocessor import SimilarityPostprocessor


def build_chat_engine(
    index: VectorStoreIndex,
    llm: LLM,
    memory: ChatSummaryMemoryBuffer,
    chat_mode: str = "condense_plus_context",
    response_mode: str = "compact",
    similarity_top_k: int = 10,
    similarity_cutoff: float = 0.1,
    verbose: bool = False,
    **kwargs: Any,
) -> BaseChatEngine:
    """Build a chat engine from a VectorStoreIndex with memory management.

    Creates a chat engine using condense_plus_context mode, which:
    1. Condenses conversation history with new user message to a standalone question
    2. Retrieves relevant documents based on the condensed question
    3. Generates response using LLM with retrieved context and conversation history
    4. Automatically saves conversation to memory

    Args:
        index: The vector store index to retrieve from
        llm: LLM instance for chat and memory summarization
        memory: ChatSummaryMemoryBuffer instance for managing conversation history
        chat_mode: Chat mode (default: "condense_plus_context")
        response_mode: Response synthesis mode (default: "compact")
                      Options: "compact", "tree_summarize", "simple_summarize", etc.
        similarity_top_k: Number of top similar nodes to retrieve (default: 10)
        similarity_cutoff: Minimum similarity score threshold (default: 0.1)
        verbose: Print debug information (default: False)
        **kwargs: Additional arguments passed to chat engine

    Returns:
        BaseChatEngine: Configured chat engine instance

    Raises:
        ValueError: If similarity_top_k < 1 or similarity_cutoff not in [0, 1]

    Example:
        >>> from newbee_notebook.core.engine import load_pgvector_index_sync
        >>> from newbee_notebook.core.llm.zhipu import build_llm
        >>> from newbee_notebook.core.rag.embeddings import build_embedding
        >>> from newbee_notebook.core.memory import build_chat_memory
        >>>
        >>> embed_model = build_embedding()
        >>> index = load_pgvector_index_sync(embed_model)
        >>> llm = build_llm()
        >>> memory = build_chat_memory(llm=llm, token_limit=64000)
        >>>
        >>> chat_engine = build_chat_engine(
        ...     index=index,
        ...     llm=llm,
        ...     memory=memory,
        ...     similarity_top_k=10,
        ...     similarity_cutoff=0.25
        ... )
        >>>
        >>> response = chat_engine.chat("What is diabetes?")
        >>> print(response)
    """
    # Validate parameters
    if similarity_top_k < 1:
        raise ValueError(
            f"similarity_top_k must be at least 1, got {similarity_top_k}"
        )

    if not 0 <= similarity_cutoff <= 1:
        raise ValueError(
            f"similarity_cutoff must be between 0 and 1, got {similarity_cutoff}"
        )

    # Create postprocessors list with similarity filter
    postprocessors = [
        SimilarityPostprocessor(similarity_cutoff=similarity_cutoff)
    ]

    # Build chat engine
    chat_engine = index.as_chat_engine(
        chat_mode=chat_mode,
        llm=llm,
        memory=memory,
        similarity_top_k=similarity_top_k,
        response_mode=response_mode,
        node_postprocessors=postprocessors,
        verbose=verbose,
        **kwargs,
    )

    return chat_engine


def build_simple_chat_engine(
    index: VectorStoreIndex,
    llm: LLM,
    memory: ChatSummaryMemoryBuffer,
) -> BaseChatEngine:
    """Build a simple chat engine with minimal configuration.

    Convenience function for quick setup with default parameters.

    Args:
        index: The vector store index
        llm: LLM instance
        memory: Chat memory buffer

    Returns:
        BaseChatEngine: Configured chat engine

    Example:
        >>> chat_engine = build_simple_chat_engine(index, llm, memory)
        >>> response = chat_engine.chat("What is diabetes?")
    """
    return build_chat_engine(
        index=index,
        llm=llm,
        memory=memory,
        similarity_top_k=5,
        similarity_cutoff=0.25,
    )


