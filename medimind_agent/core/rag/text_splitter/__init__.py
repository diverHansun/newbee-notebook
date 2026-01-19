"""Text splitter module for chunking documents into nodes.

This module provides utilities to split documents into smaller chunks
using LlamaIndex's SentenceSplitter.
"""

from medimind_agent.core.rag.text_splitter.splitter import (
    create_text_splitter,
    split_documents,
)

__all__ = [
    "create_text_splitter",
    "split_documents",
]




