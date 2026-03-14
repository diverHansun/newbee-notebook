from __future__ import annotations

import asyncio

from newbee_notebook.core.tools.contracts import (
    SourceItem,
    ToolCallResult,
    ToolDefinition,
    ToolQualityMeta,
)


def test_source_item_and_quality_meta_capture_runtime_shape():
    source = SourceItem(
        document_id="doc-1",
        chunk_id="chunk-1",
        title="Doc 1",
        text="snippet",
        score=0.91,
        source_type="retrieval",
    )
    quality = ToolQualityMeta(
        scope_used="document",
        search_type="keyword",
        result_count=3,
        max_score=0.91,
        quality_band="high",
        scope_relaxation_recommended=False,
    )

    assert source.document_id == "doc-1"
    assert source.source_type == "retrieval"
    assert quality.quality_band == "high"
    assert quality.result_count == 3


def test_tool_call_result_supports_optional_sources_and_quality_meta_for_mcp():
    result = ToolCallResult(
        content="server time: 2026-03-13T10:00:00Z",
        sources=[],
        quality_meta=None,
        metadata={"provider": "builtin"},
    )

    assert result.content.startswith("server time:")
    assert result.sources == []
    assert result.quality_meta is None
    assert result.metadata == {"provider": "builtin"}


def test_tool_definition_executes_async_contract():
    async def _execute(payload: dict) -> ToolCallResult:
        return ToolCallResult(
            content=f"hello {payload['name']}",
            sources=[],
            metadata={"echo": True},
        )

    tool = ToolDefinition(
        name="echo",
        description="Echo tool",
        parameters={"type": "object", "properties": {"name": {"type": "string"}}},
        execute=_execute,
    )

    result = asyncio.run(tool.execute({"name": "world"}))

    assert tool.name == "echo"
    assert result.content == "hello world"
    assert result.metadata == {"echo": True}
