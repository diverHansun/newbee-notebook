"""RAG (Retrieval-Augmented Generation) module for Newbee Notebook.

This module provides RAG components using LlamaIndex with pgvector and Elasticsearch backends.

Submodules:
    - embeddings: Embedding models (qwen3-embedding, Zhipu official API)
    - document_loader: Load documents from various file formats
    - text_splitter: Split documents into chunks for indexing
    - retrieval: Hybrid retrieval strategies (pgvector + ES BM25)
    - postprocessors: Filter and enhance retrieved nodes

Note:
    Index building is now handled by src.engine.index_builder using
    pgvector (PostgreSQL) and Elasticsearch backends.
"""

# Import key functions for convenience
from newbee_notebook.core.rag.embeddings import build_embedding
from newbee_notebook.core.rag.document_loader import load_documents
from newbee_notebook.core.rag.text_splitter import split_documents
from newbee_notebook.core.rag.postprocessors import (
    EvidenceConsistencyChecker,
    SourceFilterPostprocessor,
    DeduplicationPostprocessor,
)
from newbee_notebook.core.rag.retrieval import (
    HybridRetriever,
    FusionStrategy,
    RRFFusion,
    WeightedScoreFusion,
)

__all__ = [
    # Embeddings
    "build_embedding",
    # Document loading
    "load_documents",
    # Text splitting
    "split_documents",
    # Postprocessors
    "EvidenceConsistencyChecker",
    "SourceFilterPostprocessor",
    "DeduplicationPostprocessor",
    # Retrieval
    "HybridRetriever",
    "FusionStrategy",
    "RRFFusion",
    "WeightedScoreFusion",
]


