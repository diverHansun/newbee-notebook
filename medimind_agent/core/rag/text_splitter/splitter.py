"""Text splitting utilities using LlamaIndex SentenceSplitter.

This module wraps LlamaIndex's text splitting functionality to provide
consistent chunking of medical documents for indexing and retrieval.
"""

from typing import List
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core import Document
from llama_index.core.schema import BaseNode


def create_text_splitter(
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    separator: str = " ",
) -> SentenceSplitter:
    """Create a SentenceSplitter instance with specified parameters.
    
    Args:
        chunk_size: Maximum size of each text chunk in tokens
        chunk_overlap: Number of tokens to overlap between chunks
        separator: String separator for splitting (default: space)
    
    Returns:
        SentenceSplitter: Configured text splitter instance
    
    Example:
        >>> splitter = create_text_splitter(chunk_size=512, chunk_overlap=50)
    """
    return SentenceSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separator=separator,
    )


def split_documents(
    documents: List[Document],
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    separator: str = " ",
) -> List[BaseNode]:
    """Split documents into nodes (text chunks) for indexing.
    
    This function takes a list of documents and splits them into smaller
    chunks while preserving metadata and maintaining semantic coherence.
    
    Args:
        documents: List of Document objects to split
        chunk_size: Maximum size of each text chunk in tokens (default: 512)
        chunk_overlap: Number of tokens to overlap between chunks (default: 50)
        separator: String separator for splitting (default: space)
    
    Returns:
        List[BaseNode]: List of node objects representing text chunks
    
    Example:
        >>> from medimind_agent.core.rag.document_loader import load_documents
        >>> documents = load_documents("data/documents")
        >>> nodes = split_documents(documents, chunk_size=512, chunk_overlap=50)
        >>> print(f"Created {len(nodes)} nodes from {len(documents)} documents")
    
    Notes:
        - Chunk size is approximate and may vary slightly
        - Overlap helps maintain context between chunks
        - Metadata from original documents is preserved in nodes
        - Recommended chunk_size: 256-1024 depending on use case
        - Recommended chunk_overlap: 10-20% of chunk_size
    """
    # Create splitter with specified parameters
    splitter = create_text_splitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separator=separator,
    )
    
    # Split documents into nodes
    nodes = splitter.get_nodes_from_documents(documents)
    
    return nodes





