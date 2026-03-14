from __future__ import annotations

from newbee_notebook.core.engine.stream_events import (
    ContentEvent,
    DoneEvent,
    ErrorEvent,
    PhaseEvent,
    SourceEvent,
    StartEvent,
    ToolCallEvent,
    ToolResultEvent,
    WarningEvent,
)
from newbee_notebook.core.tools.contracts import SourceItem, ToolQualityMeta


def test_stream_event_types_and_payloads_are_stable():
    warning = WarningEvent(code="partial_documents", message="Some docs are still processing")
    phase = PhaseEvent(stage="retrieving")
    tool_call = ToolCallEvent(tool_name="knowledge_base", tool_call_id="call-1", tool_input={"query": "x"})
    tool_result = ToolResultEvent(
        tool_name="knowledge_base",
        tool_call_id="call-1",
        success=True,
        content_preview="top hit",
        quality_meta=ToolQualityMeta(
            scope_used="document",
            search_type="keyword",
            result_count=2,
            max_score=0.8,
            quality_band="high",
            scope_relaxation_recommended=False,
        ),
    )
    sources = SourceEvent(
        sources=[
            SourceItem(document_id="doc-1", chunk_id="chunk-1", title="Doc", text="text", score=0.8)
        ]
    )
    content = ContentEvent(delta="hello")
    done = DoneEvent()
    error = ErrorEvent(code="tool_error", message="failed", retriable=False)
    start = StartEvent(message_id="msg-1")

    assert start.event == "start"
    assert warning.event == "warning"
    assert phase.event == "phase"
    assert tool_call.event == "tool_call"
    assert tool_result.event == "tool_result"
    assert sources.event == "sources"
    assert content.event == "content"
    assert done.event == "done"
    assert error.event == "error"
    assert phase.stage == "retrieving"
    assert tool_result.quality_meta.quality_band == "high"
