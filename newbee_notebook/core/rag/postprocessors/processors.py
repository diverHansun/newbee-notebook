"""Custom postprocessors for node filtering and enhancement.

This module implements custom postprocessors that extend LlamaIndex's
BaseNodePostprocessor to provide domain-specific filtering and processing.
"""

from typing import List, Optional
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle


class EvidenceConsistencyChecker(BaseNodePostprocessor):
    """Postprocessor to check consistency between retrieved nodes.
    
    This postprocessor filters out nodes that are inconsistent with
    the majority of retrieved evidence, helping ensure factual accuracy.
    
    Attributes:
        consistency_threshold: Minimum consistency score (0-1) to keep a node
    """
    
    def __init__(self, consistency_threshold: float = 0.5):
        """Initialize the consistency checker.
        
        Args:
            consistency_threshold: Minimum consistency score to keep a node (default: 0.5)
        """
        super().__init__()
        self.consistency_threshold = consistency_threshold
    
    def _postprocess_nodes(
        self, 
        nodes: List[NodeWithScore], 
        query_bundle: Optional[QueryBundle] = None
    ) -> List[NodeWithScore]:
        """Check and filter nodes based on consistency.
        
        Args:
            nodes: List of nodes with scores to process
            query_bundle: Optional query bundle for context
            
        Returns:
            List[NodeWithScore]: Filtered list of consistent nodes
        """
        if len(nodes) < 2:
            # Not enough nodes to check consistency
            return nodes
        
        # TODO: Implement actual consistency checking logic
        # For now, return all nodes as a placeholder
        # Future implementation could use:
        # - Semantic similarity between nodes
        # - Fact extraction and comparison
        # - LLM-based consistency verification
        
        return nodes


class SourceFilterPostprocessor(BaseNodePostprocessor):
    """Postprocessor to filter nodes based on source metadata.
    
    This postprocessor filters nodes based on their source, allowing
    preference for authoritative sources and blocking unreliable ones.
    
    Attributes:
        preferred_sources: List of preferred source types (boost scores)
        blocked_sources: List of blocked source types (exclude completely)
        boost_factor: Factor to multiply scores for preferred sources
    """
    
    def __init__(
        self, 
        preferred_sources: Optional[List[str]] = None,
        blocked_sources: Optional[List[str]] = None,
        boost_factor: float = 1.2
    ):
        """Initialize the source filter.
        
        Args:
            preferred_sources: List of preferred source types
            blocked_sources: List of blocked source types
            boost_factor: Score multiplier for preferred sources (default: 1.2)
        """
        super().__init__()
        self.preferred_sources = preferred_sources or []
        self.blocked_sources = blocked_sources or []
        self.boost_factor = boost_factor
    
    def _postprocess_nodes(
        self, 
        nodes: List[NodeWithScore], 
        query_bundle: Optional[QueryBundle] = None
    ) -> List[NodeWithScore]:
        """Filter and boost nodes based on source.
        
        Args:
            nodes: List of nodes with scores to process
            query_bundle: Optional query bundle for context
            
        Returns:
            List[NodeWithScore]: Filtered and boosted nodes
        """
        filtered_nodes = []
        
        for node in nodes:
            # Get source from metadata
            source = node.node.metadata.get("source", "").lower()
            
            # Skip blocked sources
            if source in self.blocked_sources:
                continue
            
            # Boost preferred sources
            if source in self.preferred_sources:
                node.score *= self.boost_factor
            
            filtered_nodes.append(node)
        
        # Re-sort by score after boosting
        filtered_nodes.sort(key=lambda x: x.score, reverse=True)
        
        return filtered_nodes


class DeduplicationPostprocessor(BaseNodePostprocessor):
    """Postprocessor to remove duplicate or highly similar nodes.
    
    This postprocessor removes duplicate nodes based on text similarity,
    helping reduce redundancy in retrieved results.
    
    Attributes:
        similarity_threshold: Threshold above which nodes are considered duplicates
    """
    
    def __init__(self, similarity_threshold: float = 0.95):
        """Initialize the deduplication postprocessor.
        
        Args:
            similarity_threshold: Similarity threshold for deduplication (default: 0.95)
        """
        super().__init__()
        self.similarity_threshold = similarity_threshold
    
    def _postprocess_nodes(
        self, 
        nodes: List[NodeWithScore], 
        query_bundle: Optional[QueryBundle] = None
    ) -> List[NodeWithScore]:
        """Remove duplicate nodes.
        
        Args:
            nodes: List of nodes with scores to process
            query_bundle: Optional query bundle for context
            
        Returns:
            List[NodeWithScore]: Deduplicated list of nodes
        """
        if not nodes:
            return nodes
        
        # Simple deduplication based on text hash
        # TODO: Implement more sophisticated similarity-based deduplication
        seen_texts = set()
        unique_nodes = []
        
        for node in nodes:
            text_hash = hash(node.node.text)
            if text_hash not in seen_texts:
                seen_texts.add(text_hash)
                unique_nodes.append(node)
        
        return unique_nodes





