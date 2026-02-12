"""Unit tests for engine modes.

This test file validates:
- BaseMode interface and configuration
- Mode configuration defaults
- ModeType enum values

Note: These tests don't require actual LLM or database connections.
"""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from newbee_notebook.core.engine.modes.base import BaseMode, ModeConfig, ModeType
from newbee_notebook.core.engine.modes.chat_mode import ChatMode, DEFAULT_CHAT_SYSTEM_PROMPT
from newbee_notebook.core.engine.modes.ask_mode import (
    AskMode,
    DEFAULT_ASK_SYSTEM_PROMPT,
    _TitleAwareFallbackRetriever,
)
from newbee_notebook.core.engine.modes.conclude_mode import ConcludeMode, DEFAULT_CONCLUDE_SYSTEM_PROMPT
from newbee_notebook.core.engine.modes.explain_mode import ExplainMode, DEFAULT_EXPLAIN_SYSTEM_PROMPT
from newbee_notebook.core.rag.retrieval.scoped_retriever import ScopedRetriever
from llama_index.core.schema import TextNode, NodeWithScore


class TestModeType:
    """Test ModeType enum."""
    
    def test_mode_type_values(self):
        """Test that all expected mode types exist."""
        assert ModeType.CHAT.value == "chat"
        assert ModeType.ASK.value == "ask"
        assert ModeType.CONCLUDE.value == "conclude"
        assert ModeType.EXPLAIN.value == "explain"
    
    def test_mode_type_count(self):
        """Test that we have exactly 4 mode types."""
        assert len(ModeType) == 4


class TestModeConfig:
    """Test ModeConfig model."""
    
    def test_default_values(self):
        """Test ModeConfig with minimal required fields."""
        config = ModeConfig(mode_type=ModeType.CHAT)
        assert config.mode_type == ModeType.CHAT
        assert config.has_memory is True
        assert config.system_prompt is None
        assert config.verbose is False
    
    def test_custom_values(self):
        """Test ModeConfig with custom values."""
        config = ModeConfig(
            mode_type=ModeType.ASK,
            has_memory=False,
            system_prompt="Custom prompt",
            verbose=True,
        )
        assert config.mode_type == ModeType.ASK
        assert config.has_memory is False
        assert config.system_prompt == "Custom prompt"
        assert config.verbose is True


class TestChatMode:
    """Test ChatMode configuration and setup."""
    
    def test_default_config(self):
        """Test ChatMode returns correct default config."""
        mock_llm = MagicMock()
        mode = ChatMode(llm=mock_llm)
        
        assert mode.mode_type == ModeType.CHAT
        assert mode.config.has_memory is True
        assert DEFAULT_CHAT_SYSTEM_PROMPT in mode.config.system_prompt
    
    def test_custom_tools_config(self):
        """Test ChatMode with custom tool settings."""
        mock_llm = MagicMock()
        mode = ChatMode(
            llm=mock_llm,
            enable_tavily=False,
            enable_es_search=True,
            es_index_name="custom_index",
        )
        
        assert mode._enable_tavily is False
        assert mode._enable_es_search is True
        assert mode._es_index_name == "custom_index"
    
    def test_not_initialized_before_run(self):
        """Test that mode is not initialized until run is called."""
        mock_llm = MagicMock()
        mode = ChatMode(llm=mock_llm)
        
        assert mode._initialized is False
        assert mode._agent is None

    def test_collect_sources_respects_allowed_doc_scope(self):
        """_collect_sources should drop out-of-scope nodes."""
        mock_llm = MagicMock()

        class _FakeNode:
            def __init__(self, doc_id: str, node_id: str, text: str):
                self.node_id = node_id
                self.metadata = {
                    "_node_content": json.dumps({"metadata": {"document_id": doc_id}}),
                    "title": f"title-{doc_id}",
                }
                self._text = text

            def get_content(self):
                return self._text

        class _FakeRetriever:
            def retrieve(self, _message):
                return [
                    MagicMock(node=_FakeNode("doc-1", "chunk-1", "text-1"), score=0.9),
                    MagicMock(node=_FakeNode("doc-2", "chunk-2", "text-2"), score=0.7),
                ]

        class _FakeVectorIndex:
            def as_retriever(self, **_kwargs):
                return _FakeRetriever()

        mode = ChatMode(llm=mock_llm, vector_index=_FakeVectorIndex())
        mode.set_allowed_documents(["doc-1"])

        sources = mode._collect_sources("hello")
        assert len(sources) == 1
        assert sources[0]["document_id"] == "doc-1"


class TestAskMode:
    """Test AskMode configuration and setup."""
    
    def test_default_config(self):
        """Test AskMode returns correct default config."""
        mock_llm = MagicMock()
        mode = AskMode(llm=mock_llm)
        
        assert mode.mode_type == ModeType.ASK
        assert mode.config.has_memory is True
        assert DEFAULT_ASK_SYSTEM_PROMPT in mode.config.system_prompt
    
    def test_retrieval_settings(self):
        """Test AskMode retrieval configuration."""
        mock_llm = MagicMock()
        mode = AskMode(
            llm=mock_llm,
            pgvector_top_k=15,
            es_top_k=15,
            final_top_k=10,
        )
        
        assert mode._pgvector_top_k == 15
        assert mode._es_top_k == 15
        assert mode._final_top_k == 10

    def test_build_title_fallback_query_from_context(self):
        """Ask mode should build a compact fallback query from title hints."""
        mode = AskMode(llm=MagicMock())
        mode.set_context(
            {
                "allowed_document_titles": [
                    "Doc A",
                    "Doc B",
                    "Doc A",
                ]
            }
        )

        fallback_query = mode._build_title_fallback_query("what is differential diagnosis")
        assert fallback_query == "Doc A Doc B what is differential diagnosis"

    def test_build_title_fallback_query_without_titles(self):
        """No title hints should disable fallback query construction."""
        mode = AskMode(llm=MagicMock())
        mode.set_context({})

        assert mode._build_title_fallback_query("question") is None

    def test_title_aware_fallback_retriever_retries_once(self):
        """Fallback retriever should retry with title-boosted query on empty hit."""

        class _BaseRetriever:
            def __init__(self):
                self.queries = []

            def _build_result(self):
                node = TextNode(
                    text="matched",
                    metadata={
                        "_node_content": json.dumps(
                            {"metadata": {"document_id": "doc-1"}}
                        )
                    },
                )
                return [NodeWithScore(node=node, score=1.0)]

            def retrieve(self, query_bundle):
                query = getattr(query_bundle, "query_str", str(query_bundle))
                self.queries.append(query)
                if query.startswith("Doc A "):
                    return self._build_result()
                return []

            async def aretrieve(self, query_bundle):
                return self.retrieve(query_bundle)

        base_retriever = _BaseRetriever()
        retriever = _TitleAwareFallbackRetriever(
            base_retriever=base_retriever,
            fallback_query_builder=lambda query: f"Doc A {query}",
        )

        results = retriever.retrieve("what is differential diagnosis")

        assert len(results) == 1
        assert base_retriever.queries == [
            "what is differential diagnosis",
            "Doc A what is differential diagnosis",
        ]
        assert retriever.last_fallback_query == "Doc A what is differential diagnosis"


class TestConcludeMode:
    """Test ConcludeMode configuration and setup."""
    
    def test_default_config(self):
        """Test ConcludeMode returns correct default config."""
        mock_llm = MagicMock()
        mode = ConcludeMode(llm=mock_llm)
        
        assert mode.mode_type == ModeType.CONCLUDE
        assert mode.config.has_memory is True
        assert DEFAULT_CONCLUDE_SYSTEM_PROMPT in mode.config.system_prompt
    
    def test_memory_is_preserved(self):
        """Test that provided memory is retained for ConcludeMode."""
        mock_llm = MagicMock()
        mock_memory = MagicMock()
        
        mode = ConcludeMode(llm=mock_llm, memory=mock_memory)
        
        assert mode.memory is mock_memory
        assert mode.has_memory is True
    
    def test_similarity_settings(self):
        """Test ConcludeMode retrieval settings."""
        mock_llm = MagicMock()
        mode = ConcludeMode(
            llm=mock_llm,
            similarity_top_k=15,
        )
        
        assert mode._similarity_top_k == 15

    def test_conclude_mode_wraps_retriever_with_scope(self):
        """Conclude mode should enforce notebook scope via ScopedRetriever."""
        mock_llm = MagicMock()
        base_retriever = MagicMock()
        fake_index = MagicMock()
        fake_index.as_retriever.return_value = base_retriever

        mode = ConcludeMode(llm=mock_llm, index=fake_index)
        mode.set_allowed_documents(["doc-1"])

        with patch(
            "newbee_notebook.core.engine.modes.conclude_mode.CondensePlusContextChatEngine.from_defaults",
            return_value=MagicMock(),
        ):
            import asyncio

            asyncio.run(mode._refresh_engine())

        assert isinstance(mode._retriever, ScopedRetriever)


class TestExplainMode:
    """Test ExplainMode configuration and setup."""
    
    def test_default_config(self):
        """Test ExplainMode returns correct default config."""
        mock_llm = MagicMock()
        mode = ExplainMode(llm=mock_llm)
        
        assert mode.mode_type == ModeType.EXPLAIN
        assert mode.config.has_memory is True
        assert DEFAULT_EXPLAIN_SYSTEM_PROMPT in mode.config.system_prompt
    
    def test_memory_is_preserved(self):
        """Test that provided memory is retained for ExplainMode."""
        mock_llm = MagicMock()
        mock_memory = MagicMock()
        
        mode = ExplainMode(llm=mock_llm, memory=mock_memory)
        
        assert mode.memory is mock_memory
        assert mode.has_memory is True
    
    def test_query_settings(self):
        """Test ExplainMode retrieval settings."""
        mock_llm = MagicMock()
        mode = ExplainMode(
            llm=mock_llm,
            similarity_top_k=3,
        )
        
        assert mode._similarity_top_k == 3


class TestModeMemoryBehavior:
    """Test memory behavior across different modes."""
    
    def test_chat_mode_has_memory(self):
        """Test Chat mode maintains memory."""
        mock_llm = MagicMock()
        mock_memory = MagicMock()
        
        mode = ChatMode(llm=mock_llm, memory=mock_memory)
        
        assert mode.has_memory is True
    
    def test_ask_mode_has_memory(self):
        """Test Ask mode maintains memory."""
        mock_llm = MagicMock()
        mock_memory = MagicMock()
        
        mode = AskMode(llm=mock_llm, memory=mock_memory)
        
        assert mode.has_memory is True
    
    def test_conclude_mode_has_memory(self):
        """Test Conclude mode uses memory."""
        mock_llm = MagicMock()
        mock_memory = MagicMock()
        
        mode = ConcludeMode(llm=mock_llm, memory=mock_memory)
        
        assert mode.has_memory is True
    
    def test_explain_mode_has_memory(self):
        """Test Explain mode uses memory."""
        mock_llm = MagicMock()
        mock_memory = MagicMock()
        
        mode = ExplainMode(llm=mock_llm, memory=mock_memory)
        
        assert mode.has_memory is True


