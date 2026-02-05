"""Document loader module for loading markdown documents.

This module provides utilities to load markdown documents using LlamaIndex's
MarkdownReader. All source documents are now converted to unified markdown
format before loading (via MinerU for PDF, MarkItDown for Office docs).
"""

from medimind_agent.core.rag.document_loader.loader import (
    load_documents,
    load_documents_from_subdirs,
)

__all__ = [
    "load_documents",
    "load_documents_from_subdirs",
]



