from __future__ import annotations

import pytest

from newbee_notebook.core.tools.builtin_provider import BuiltinToolProvider
from newbee_notebook.core.tools.contracts import ToolCallResult
from newbee_notebook.core.tools.knowledge_base import build_knowledge_base_tool


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_knowledge_base_routes_search_type_and_formats_results():
    calls: list[tuple[str, dict]] = []

    async def _search(search_type: str, payload: dict):
        calls.append((search_type, payload))
        return [
            {
                "document_id": "doc-1",
                "chunk_id": "chunk-1",
                "title": "Doc 1",
                "text": "retrieved evidence",
                "score": 0.88,
            }
        ]

    tool = build_knowledge_base_tool(
        hybrid_search=lambda payload: _search("hybrid", payload),
        semantic_search=lambda payload: _search("semantic", payload),
        keyword_search=lambda payload: _search("keyword", payload),
    )

    result = await tool.execute(
        {
            "query": "what happened",
            "search_type": "keyword",
            "max_results": 3,
        }
    )

    assert calls == [
        (
            "keyword",
            {
                "query": "what happened",
                "search_type": "keyword",
                "max_results": 3,
                "allowed_document_ids": None,
                "filter_document_id": None,
            },
        )
    ]
    assert isinstance(result, ToolCallResult)
    assert "Doc 1" in result.content
    assert "retrieved evidence" in result.content
    assert result.sources[0].document_id == "doc-1"
    assert result.sources[0].chunk_id == "chunk-1"
    assert result.quality_meta is not None
    assert result.quality_meta.scope_used == "notebook"
    assert result.quality_meta.search_type == "keyword"
    assert result.quality_meta.result_count == 1
    assert result.quality_meta.quality_band == "medium"
    assert result.quality_meta.scope_relaxation_recommended is False


@pytest.mark.anyio
async def test_knowledge_base_binds_document_scope_within_allowed_document_ids():
    calls: list[dict] = []

    async def _semantic(payload: dict):
        calls.append(payload)
        return []

    tool = build_knowledge_base_tool(
        semantic_search=_semantic,
        allowed_document_ids=["doc-1", "doc-2"],
        default_search_type="semantic",
    )

    result = await tool.execute(
        {
            "query": "focus",
            "filter_document_id": "doc-2",
        }
    )

    assert calls == [
        {
            "query": "focus",
            "search_type": "semantic",
            "max_results": 5,
            "allowed_document_ids": ["doc-2"],
            "filter_document_id": "doc-2",
        }
    ]
    assert result.sources == []
    assert result.quality_meta is not None
    assert result.quality_meta.scope_used == "document"
    assert result.quality_meta.quality_band == "empty"
    assert result.quality_meta.scope_relaxation_recommended is True


@pytest.mark.anyio
async def test_knowledge_base_short_circuits_when_filter_document_is_out_of_scope():
    async def _semantic(_payload: dict):
        raise AssertionError("search should not run when document filter is out of scope")

    tool = build_knowledge_base_tool(
        semantic_search=_semantic,
        allowed_document_ids=["doc-1"],
        default_search_type="semantic",
    )

    result = await tool.execute(
        {
            "query": "focus",
            "filter_document_id": "doc-x",
        }
    )

    assert result.sources == []
    assert result.quality_meta is not None
    assert result.quality_meta.scope_used == "document"
    assert result.quality_meta.quality_band == "empty"
    assert result.quality_meta.scope_relaxation_recommended is True


@pytest.mark.anyio
async def test_builtin_provider_applies_mode_specific_defaults_and_allows_overrides():
    calls: list[dict] = []

    async def _search(payload: dict):
        calls.append(payload)
        return []

    provider = BuiltinToolProvider(
        hybrid_search=_search,
        semantic_search=_search,
        keyword_search=_search,
    )

    explain_tool = provider.get_tools("explain")[0]
    conclude_tool = provider.get_tools("conclude")[0]

    await explain_tool.execute({"query": "explain this"})
    await conclude_tool.execute({"query": "summarize this"})
    await explain_tool.execute({"query": "override", "search_type": "hybrid", "max_results": 9})

    assert calls[0]["search_type"] == "keyword"
    assert calls[0]["max_results"] == 5
    assert calls[1]["search_type"] == "hybrid"
    assert calls[1]["max_results"] == 8
    assert calls[2]["search_type"] == "hybrid"
    assert calls[2]["max_results"] == 9


def test_knowledge_base_tool_exposes_argument_documentation():
    tool = build_knowledge_base_tool()

    assert "query" in tool.description
    assert "search_type" in tool.description
    assert "max_results" in tool.description
    assert "filter_document_id" in tool.description
    assert "allowed_document_ids" in tool.description
    assert "keyword" in tool.parameters["properties"]["search_type"]["description"]
    assert "semantic" in tool.parameters["properties"]["search_type"]["description"]
    assert "hybrid" in tool.parameters["properties"]["search_type"]["description"]
    assert "precise" in tool.parameters["properties"]["query"]["description"].lower()
