"""Unit tests for tools layer components."""

import pytest
from unittest.mock import AsyncMock

import newbee_notebook.core.tools as tools_module
from newbee_notebook.core.tools import BuiltinToolProvider, ToolRegistry
from newbee_notebook.core.rag.retrieval.es_keyword import es_search


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_tools_module_no_longer_exports_legacy_function_tool_builders():
    assert not hasattr(tools_module, "build_tavily_search_tool")
    assert not hasattr(tools_module, "build_tavily_news_tool")
    assert not hasattr(tools_module, "build_tavily_crawl_tool")
    assert not hasattr(tools_module, "build_zhipu_web_search_tool")
    assert not hasattr(tools_module, "build_zhipu_web_crawl_tool")


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



