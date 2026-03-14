"""Unit tests for tools layer components."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from newbee_notebook.core.tools import BuiltinToolProvider, ToolRegistry
from newbee_notebook.core.tools.tavily_tools import TavilySearchTool, build_tavily_tool
from newbee_notebook.core.rag.retrieval.es_keyword import es_search


@pytest.fixture
def anyio_backend():
    return "asyncio"


class TestTavilySearchTool:
    """Test TavilySearchTool functionality."""
    
    def test_tool_creation(self):
        """Test TavilySearchTool instantiation."""
        tool = TavilySearchTool(max_results=3)
        assert tool.max_results == 3
    
    def test_get_tool_returns_function_tool(self):
        """Test that get_tool returns a FunctionTool."""
        with patch.dict("os.environ", {"TAVILY_API_KEY": "test_key"}):
            tool = TavilySearchTool()
            function_tool = tool.get_tool()
            
            assert function_tool is not None
            assert function_tool.metadata.name == "web_search"
            assert "web" in function_tool.metadata.description.lower()
    
    def test_tool_is_cached(self):
        """Test that the same FunctionTool instance is returned."""
        tool = TavilySearchTool()
        with patch.dict("os.environ", {"TAVILY_API_KEY": "test_key"}):
            ft1 = tool.get_tool()
            ft2 = tool.get_tool()
            assert ft1 is ft2  # Same instance
    
    def test_build_tavily_tool_convenience(self):
        """Test build_tavily_tool convenience function."""
        with patch.dict("os.environ", {"TAVILY_API_KEY": "test_key"}):
            function_tool = build_tavily_tool(max_results=5)
            assert function_tool.metadata.name == "web_search"


class TestElasticsearchKeywordRetrieval:
    def test_es_search_scopes_results_to_allowed_documents(self, monkeypatch):
        captured = {}

        class _FakeIndices:
            @staticmethod
            def exists(index):
                return True

        class _FakeElasticsearch:
            def __init__(self, _hosts):
                self.indices = _FakeIndices()

            def search(self, index, body):
                captured["index"] = index
                captured["body"] = body
                return {
                    "hits": {
                        "hits": [
                            {
                                "_score": 1.0,
                                "_source": {
                                    "content": "doc 1",
                                    "metadata": {"title": "Doc1", "source_document_id": "doc-1"},
                                },
                            },
                            {
                                "_score": 0.9,
                                "_source": {
                                    "content": "doc 2",
                                    "metadata": {"title": "Doc2", "source_document_id": "doc-2"},
                                },
                            },
                        ]
                    }
                }

        monkeypatch.setattr(
            "newbee_notebook.core.rag.retrieval.es_keyword.Elasticsearch",
            _FakeElasticsearch,
        )

        result = es_search(
            query="test",
            index_name="newbee_notebook_docs",
            max_results=5,
            es_url="http://localhost:9200",
            allowed_doc_ids=["doc-1"],
        )

        assert "Doc1" in result
        assert "Doc2" not in result
        filters = captured["body"]["query"]["bool"]["filter"]
        assert filters and "should" in filters[0]["bool"]
        should_terms = filters[0]["bool"]["should"]
        assert any("metadata.source_document_id.keyword" in item.get("terms", {}) for item in should_terms)
        assert any("metadata.source_document_id" in item.get("terms", {}) for item in should_terms)

    def test_es_search_returns_fast_when_scope_is_empty(self, monkeypatch):
        class _FailElasticsearch:
            def __init__(self, _hosts):
                raise AssertionError("Elasticsearch should not be initialized for empty scope")

        monkeypatch.setattr(
            "newbee_notebook.core.rag.retrieval.es_keyword.Elasticsearch",
            _FailElasticsearch,
        )

        result = es_search(
            query="test",
            allowed_doc_ids=[],
        )
        assert "No notebook-scoped documents are available" in result


class TestRuntimeToolRegistry:
    @pytest.mark.anyio
    async def test_ask_mode_gets_knowledge_base_and_time_only(self):
        provider = BuiltinToolProvider(
            hybrid_search=AsyncMock(),
            semantic_search=AsyncMock(),
            keyword_search=AsyncMock(),
        )
        registry = ToolRegistry(builtin_provider=provider)

        tools = await registry.get_tools("ask")

        assert [tool.name for tool in tools] == ["knowledge_base", "time"]



