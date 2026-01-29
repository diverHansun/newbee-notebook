"""Retrieval module for RAG pipelines.

This module provides retrieval components including:
- HybridRetriever: Combines pgvector semantic search with ES BM25
- Fusion strategies for merging results from multiple sources
"""

from medimind_agent.core.rag.retrieval.hybrid_retriever import HybridRetriever, build_hybrid_retriever
from medimind_agent.core.rag.retrieval.filters import build_document_filters
from medimind_agent.core.rag.retrieval.fusion import (
    FusionStrategy,
    RRFFusion,
    WeightedScoreFusion,
)

__all__ = [
    "HybridRetriever",
    "build_hybrid_retriever",
    "build_document_filters",
    "FusionStrategy",
    "RRFFusion",
    "WeightedScoreFusion",
]


