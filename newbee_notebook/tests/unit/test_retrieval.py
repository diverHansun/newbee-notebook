"""Unit tests for retrieval layer components.

This test file validates:
- RRFFusion strategy
- WeightedScoreFusion strategy
- Result ordering and score calculation
"""

import pytest
from unittest.mock import MagicMock

from llama_index.core.schema import NodeWithScore, TextNode

from newbee_notebook.core.rag.retrieval.fusion import RRFFusion, WeightedScoreFusion


def create_mock_node(node_id: str, text: str, score: float) -> NodeWithScore:
    """Helper to create mock NodeWithScore objects."""
    node = TextNode(id_=node_id, text=text)
    return NodeWithScore(node=node, score=score)


class TestRRFFusion:
    """Test RRFFusion strategy."""
    
    def test_single_source(self):
        """Test RRF with single source returns same order."""
        fusion = RRFFusion(k=60)
        
        results = [
            create_mock_node("doc1", "Document 1", 0.9),
            create_mock_node("doc2", "Document 2", 0.8),
            create_mock_node("doc3", "Document 3", 0.7),
        ]
        
        fused = fusion.fuse([results], top_k=3)
        
        assert len(fused) == 3
        assert fused[0].node.node_id == "doc1"
        assert fused[1].node.node_id == "doc2"
        assert fused[2].node.node_id == "doc3"
    
    def test_two_sources_different_order(self):
        """Test RRF combines rankings from two sources."""
        fusion = RRFFusion(k=60)
        
        # Source 1: doc1 > doc2 > doc3
        source1 = [
            create_mock_node("doc1", "Document 1", 0.9),
            create_mock_node("doc2", "Document 2", 0.8),
            create_mock_node("doc3", "Document 3", 0.7),
        ]
        
        # Source 2: doc2 > doc3 > doc1 (different order)
        source2 = [
            create_mock_node("doc2", "Document 2", 0.95),
            create_mock_node("doc3", "Document 3", 0.85),
            create_mock_node("doc1", "Document 1", 0.75),
        ]
        
        fused = fusion.fuse([source1, source2], top_k=3)
        
        # doc2 should be first (rank 1 + rank 2 in sources)
        # doc1 should be second (rank 1 + rank 3 in sources)
        assert len(fused) == 3
        assert fused[0].node.node_id == "doc2"  # Best combined rank
    
    def test_unique_documents_from_sources(self):
        """Test RRF handles documents unique to one source."""
        fusion = RRFFusion(k=60)
        
        # Source 1 has doc1, doc2
        source1 = [
            create_mock_node("doc1", "Document 1", 0.9),
            create_mock_node("doc2", "Document 2", 0.8),
        ]
        
        # Source 2 has doc3, doc4 (completely different)
        source2 = [
            create_mock_node("doc3", "Document 3", 0.95),
            create_mock_node("doc4", "Document 4", 0.85),
        ]
        
        fused = fusion.fuse([source1, source2], top_k=4)
        
        assert len(fused) == 4
        # All documents should be present
        node_ids = [n.node.node_id for n in fused]
        assert set(node_ids) == {"doc1", "doc2", "doc3", "doc4"}
    
    def test_top_k_limiting(self):
        """Test that top_k limits results."""
        fusion = RRFFusion(k=60)
        
        results = [
            create_mock_node(f"doc{i}", f"Document {i}", 0.9 - i * 0.1)
            for i in range(10)
        ]
        
        fused = fusion.fuse([results], top_k=3)
        
        assert len(fused) == 3
    
    def test_empty_results(self):
        """Test RRF handles empty results gracefully."""
        fusion = RRFFusion(k=60)
        
        fused = fusion.fuse([[], []], top_k=5)
        
        assert len(fused) == 0


class TestWeightedScoreFusion:
    """Test WeightedScoreFusion strategy."""
    
    def test_equal_weights(self):
        """Test fusion with equal weights."""
        fusion = WeightedScoreFusion()
        
        source1 = [
            create_mock_node("doc1", "Document 1", 1.0),
            create_mock_node("doc2", "Document 2", 0.5),
        ]
        
        source2 = [
            create_mock_node("doc1", "Document 1", 0.5),
            create_mock_node("doc2", "Document 2", 1.0),
        ]
        
        fused = fusion.fuse([source1, source2], top_k=2)
        
        assert len(fused) == 2
        # With equal weights, both should have equal score
        # Both docs appear in both sources with average scores
    
    def test_custom_weights(self):
        """Test fusion with custom weights."""
        fusion = WeightedScoreFusion(weights=[0.8, 0.2])
        
        source1 = [
            create_mock_node("doc1", "Document 1", 1.0),
        ]
        
        source2 = [
            create_mock_node("doc2", "Document 2", 1.0),
        ]
        
        fused = fusion.fuse([source1, source2], top_k=2)
        
        # doc1 should have higher score (0.8 weight)
        assert fused[0].node.node_id == "doc1"
    
    def test_empty_results(self):
        """Test weighted fusion handles empty results."""
        fusion = WeightedScoreFusion()
        
        fused = fusion.fuse([[], []], top_k=5)
        
        assert len(fused) == 0


