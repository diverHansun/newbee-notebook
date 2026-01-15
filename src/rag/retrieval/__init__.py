"""Retrieval module for RAG pipelines.

This module provides retrieval components including:
- HybridRetriever: Combines pgvector semantic search with ES BM25
- Fusion strategies for merging results from multiple sources
"""

from src.rag.retrieval.hybrid_retriever import HybridRetriever, build_hybrid_retriever
from src.rag.retrieval.fusion import (
    FusionStrategy,
    RRFFusion,
    WeightedScoreFusion,
)

__all__ = [
    "HybridRetriever",
    "build_hybrid_retriever",
    "FusionStrategy",
    "RRFFusion",
    "WeightedScoreFusion",
]
