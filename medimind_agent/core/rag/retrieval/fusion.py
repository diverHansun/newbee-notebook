"""Fusion strategies for combining retrieval results.

This module provides different strategies for merging results from
multiple retrieval sources (e.g., pgvector and Elasticsearch).

Following the Strategy Pattern (OCP principle) to allow easy addition
of new fusion methods without modifying existing code.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from llama_index.core.schema import NodeWithScore


class FusionStrategy(ABC):
    """Abstract base class for fusion strategies.
    
    Implements the Strategy Pattern to allow different fusion algorithms
    to be used interchangeably.
    """
    
    @abstractmethod
    def fuse(
        self,
        results_list: List[List[NodeWithScore]],
        top_k: int = 10,
    ) -> List[NodeWithScore]:
        """Fuse multiple result lists into a single ranked list.
        
        Args:
            results_list: List of result lists from different retrievers
            top_k: Number of results to return
            
        Returns:
            Fused and re-ranked list of NodeWithScore
        """
        pass


class RRFFusion(FusionStrategy):
    """Reciprocal Rank Fusion (RRF) strategy.
    
    RRF is a simple but effective fusion method that combines rankings
    from multiple sources. It's robust to score normalization issues
    across different retrieval systems.
    
    Formula: RRF(d) = sum(1 / (k + rank(d, r)) for r in rankings)
    where k is a constant (default 60) and rank(d, r) is the rank of
    document d in ranking r.
    
    Reference: "Reciprocal Rank Fusion outperforms Condorcet and
    individual Rank Learning Methods" (Cormack et al., 2009)
    """
    
    def __init__(self, k: int = 60):
        """Initialize RRFFusion.
        
        Args:
            k: Ranking constant (default: 60). Higher values give more
               weight to lower-ranked documents.
        """
        self.k = k
    
    def fuse(
        self,
        results_list: List[List[NodeWithScore]],
        top_k: int = 10,
    ) -> List[NodeWithScore]:
        """Fuse results using Reciprocal Rank Fusion.
        
        Args:
            results_list: List of result lists from different retrievers
            top_k: Number of results to return
            
        Returns:
            Fused list of NodeWithScore sorted by RRF score
        """
        # Calculate RRF scores for each document
        rrf_scores: Dict[str, float] = {}
        node_map: Dict[str, NodeWithScore] = {}
        
        for results in results_list:
            for rank, node_with_score in enumerate(results, start=1):
                node_id = node_with_score.node.node_id
                
                # Calculate RRF contribution from this ranking
                rrf_contribution = 1.0 / (self.k + rank)
                
                if node_id in rrf_scores:
                    rrf_scores[node_id] += rrf_contribution
                else:
                    rrf_scores[node_id] = rrf_contribution
                    node_map[node_id] = node_with_score
        
        # Sort by RRF score (descending)
        sorted_ids = sorted(
            rrf_scores.keys(),
            key=lambda x: rrf_scores[x],
            reverse=True,
        )
        
        # Build result list with updated scores
        fused_results = []
        for node_id in sorted_ids[:top_k]:
            node_with_score = node_map[node_id]
            # Update score to RRF score
            fused_results.append(
                NodeWithScore(
                    node=node_with_score.node,
                    score=rrf_scores[node_id],
                )
            )
        
        return fused_results


class WeightedScoreFusion(FusionStrategy):
    """Weighted score fusion strategy.
    
    Combines scores from multiple sources using weighted averaging.
    Requires score normalization for fair comparison.
    
    Note: This strategy assumes scores are normalized to [0, 1] range.
    """
    
    def __init__(self, weights: Optional[List[float]] = None):
        """Initialize WeightedScoreFusion.
        
        Args:
            weights: List of weights for each result source.
                     If None, equal weights are used.
        """
        self.weights = weights
    
    def fuse(
        self,
        results_list: List[List[NodeWithScore]],
        top_k: int = 10,
    ) -> List[NodeWithScore]:
        """Fuse results using weighted score averaging.
        
        Args:
            results_list: List of result lists from different retrievers
            top_k: Number of results to return
            
        Returns:
            Fused list of NodeWithScore sorted by weighted score
        """
        # Use equal weights if not specified
        weights = self.weights
        if weights is None:
            weights = [1.0 / len(results_list)] * len(results_list)
        
        # Ensure weights are normalized
        weight_sum = sum(weights)
        weights = [w / weight_sum for w in weights]
        
        # Normalize scores within each result list
        normalized_results = []
        for results in results_list:
            if not results:
                normalized_results.append([])
                continue
                
            max_score = max(r.score for r in results) if results else 1.0
            min_score = min(r.score for r in results) if results else 0.0
            score_range = max_score - min_score if max_score != min_score else 1.0
            
            normalized = []
            for r in results:
                norm_score = (r.score - min_score) / score_range
                normalized.append(
                    NodeWithScore(node=r.node, score=norm_score)
                )
            normalized_results.append(normalized)
        
        # Calculate weighted scores
        weighted_scores: Dict[str, float] = {}
        node_map: Dict[str, NodeWithScore] = {}
        
        for weight, results in zip(weights, normalized_results):
            for node_with_score in results:
                node_id = node_with_score.node.node_id
                weighted_contribution = weight * node_with_score.score
                
                if node_id in weighted_scores:
                    weighted_scores[node_id] += weighted_contribution
                else:
                    weighted_scores[node_id] = weighted_contribution
                    node_map[node_id] = node_with_score
        
        # Sort by weighted score (descending)
        sorted_ids = sorted(
            weighted_scores.keys(),
            key=lambda x: weighted_scores[x],
            reverse=True,
        )
        
        # Build result list
        fused_results = []
        for node_id in sorted_ids[:top_k]:
            node_with_score = node_map[node_id]
            fused_results.append(
                NodeWithScore(
                    node=node_with_score.node,
                    score=weighted_scores[node_id],
                )
            )
        
        return fused_results
from typing import Optional


