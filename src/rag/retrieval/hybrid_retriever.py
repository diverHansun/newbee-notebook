"""Hybrid retriever combining pgvector and Elasticsearch.

This module provides a retriever that combines semantic search (pgvector)
with keyword search (Elasticsearch BM25) for improved retrieval quality.

The hybrid approach leverages:
- pgvector: Semantic understanding and similarity matching
- Elasticsearch: Keyword matching and BM25 relevance scoring
"""

import asyncio
from typing import List, Optional, Any
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle
from llama_index.core.callbacks import CallbackManager
from llama_index.core.vector_stores.types import (
    VectorStoreQuery,
    VectorStoreQueryMode,
)

from src.rag.retrieval.fusion import FusionStrategy, RRFFusion


class HybridRetriever(BaseRetriever):
    """Hybrid retriever combining pgvector semantic search with ES BM25.
    
    This retriever executes queries against both pgvector (for semantic
    similarity) and Elasticsearch (for BM25 keyword matching), then fuses
    the results using a configurable fusion strategy.
    
    Attributes:
        pgvector_retriever: Retriever for pgvector semantic search
        es_retriever: Retriever for Elasticsearch BM25 search
        fusion_strategy: Strategy for combining results
        top_k: Number of results to return after fusion
    """
    
    def __init__(
        self,
        pgvector_retriever: BaseRetriever,
        es_retriever: BaseRetriever,
        fusion_strategy: Optional[FusionStrategy] = None,
        top_k: int = 10,
        callback_manager: Optional[CallbackManager] = None,
    ):
        """Initialize HybridRetriever.
        
        Args:
            pgvector_retriever: Retriever for pgvector semantic search
            es_retriever: Retriever for Elasticsearch BM25
            fusion_strategy: Strategy for fusing results (default: RRFFusion)
            top_k: Number of final results to return
            callback_manager: Optional callback manager
        """
        super().__init__(callback_manager=callback_manager)
        
        self._pgvector_retriever = pgvector_retriever
        self._es_retriever = es_retriever
        self._fusion_strategy = fusion_strategy or RRFFusion()
        self._top_k = top_k
    
    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Retrieve and fuse results from both sources.
        
        This is the synchronous retrieval method required by BaseRetriever.
        
        Args:
            query_bundle: Query bundle containing the query string
            
        Returns:
            List of NodeWithScore, fused and ranked
        """
        # Get results from both retrievers
        pgvector_results = self._pgvector_retriever.retrieve(query_bundle)
        es_results = self._es_retriever.retrieve(query_bundle)
        
        # Fuse results
        fused_results = self._fusion_strategy.fuse(
            results_list=[pgvector_results, es_results],
            top_k=self._top_k,
        )
        
        return fused_results
    
    async def _aretrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Asynchronously retrieve and fuse results from both sources.
        
        Executes both retrievals in parallel for better performance.
        
        Args:
            query_bundle: Query bundle containing the query string
            
        Returns:
            List of NodeWithScore, fused and ranked
        """
        # Execute both retrievals in parallel
        pgvector_task = self._pgvector_retriever.aretrieve(query_bundle)
        es_task = self._es_retriever.aretrieve(query_bundle)
        
        pgvector_results, es_results = await asyncio.gather(
            pgvector_task,
            es_task,
        )
        
        # Fuse results
        fused_results = self._fusion_strategy.fuse(
            results_list=[pgvector_results, es_results],
            top_k=self._top_k,
        )
        
        return fused_results


def build_hybrid_retriever(
    pgvector_index: Any,
    es_index: Any,
    pgvector_top_k: int = 10,
    es_top_k: int = 10,
    final_top_k: int = 10,
    fusion_strategy: Optional[FusionStrategy] = None,
    similarity_cutoff: Optional[float] = None,
) -> HybridRetriever:
    """Build a hybrid retriever from pgvector and Elasticsearch indexes.
    
    Convenience function for creating a HybridRetriever with common settings.
    
    Args:
        pgvector_index: VectorStoreIndex backed by pgvector
        es_index: VectorStoreIndex backed by Elasticsearch
        pgvector_top_k: Number of results from pgvector (default: 10)
        es_top_k: Number of results from Elasticsearch (default: 10)
        final_top_k: Number of final fused results (default: 10)
        fusion_strategy: Fusion strategy (default: RRFFusion)
        similarity_cutoff: Optional similarity threshold for pgvector
        
    Returns:
        Configured HybridRetriever instance
        
    Example:
        >>> from llama_index.core import VectorStoreIndex
        >>> pgvector_index = VectorStoreIndex.from_vector_store(pgvector_store)
        >>> es_index = VectorStoreIndex.from_vector_store(es_store)
        >>> retriever = build_hybrid_retriever(
        ...     pgvector_index=pgvector_index,
        ...     es_index=es_index,
        ...     final_top_k=10,
        ... )
    """
    # Create pgvector retriever
    pgvector_retriever = pgvector_index.as_retriever(
        similarity_top_k=pgvector_top_k,
    )
    
    # Create ES retriever
    es_retriever = es_index.as_retriever(
        similarity_top_k=es_top_k,
    )
    
    # Build hybrid retriever
    return HybridRetriever(
        pgvector_retriever=pgvector_retriever,
        es_retriever=es_retriever,
        fusion_strategy=fusion_strategy or RRFFusion(),
        top_k=final_top_k,
    )
