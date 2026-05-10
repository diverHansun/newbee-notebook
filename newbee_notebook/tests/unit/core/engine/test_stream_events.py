from __future__ import annotations

from newbee_notebook.core.engine.stream_events import (
    ContentEvent,
    DoneEvent,
    ErrorEvent,
    ImageGeneratedEvent,
    PermissionRequestEvent,
    PhaseEvent,
    SourceEvent,
    StartEvent,
    ToolCallEvent,
    ToolResultEvent,
    WarningEvent,
)
from newbee_notebook.core.tools.contracts import ImageResult, SourceItem, ToolQualityMeta


def test_stream_event_types_and_payloads_are_stable():
    warning = WarningEvent(code="partial_documents", message="Some docs are still processing")
    phase = PhaseEvent(stage="retrieving")
    tool_call = ToolCallEvent(tool_name="knowledge_base", tool_call_id="call-1", tool_input={"query": "x"})
    tool_result = ToolResultEvent(
        tool_name="knowledge_base",
        tool_call_id="call-1",
        success=True,
        content_preview="top hit",
        error_code=None,
        metadata={"result_count": 2},
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
    permission_request = PermissionRequestEvent(
        request_id="req-1",
        tool_name="delete_note",
        args_summary={"note_id": "n1"},
        description="Agent requested to run delete_note",
    )
    image_generated = ImageGeneratedEvent(
        images=[
            ImageResult(
                image_id="img-1",
                storage_key="generated-images/nb/sess/img-1.png",
                prompt="draw a cat",
                provider="qwen",
                model="qwen-image-2.0-pro",
                width=1024,
                height=1024,
            )
        ],
        tool_call_id="call-2",
        tool_name="image_generate",
    )

    assert start.event == "start"
    assert warning.event == "warning"
    assert phase.event == "phase"
    assert tool_call.event == "tool_call"
    assert tool_result.event == "tool_result"
    assert permission_request.event == "permission_request"
    assert image_generated.event == "image_generated"
    assert sources.event == "sources"
    assert content.event == "content"
    assert done.event == "done"
    assert error.event == "error"
    assert phase.stage == "retrieving"
    assert permission_request.request_id == "req-1"
    assert image_generated.tool_name == "image_generate"
    assert image_generated.images[0].image_id == "img-1"
    assert tool_result.quality_meta.quality_band == "high"
    assert tool_result.metadata["result_count"] == 2


def test_permission_request_event_is_the_canonical_permission_event():
    event = PermissionRequestEvent(
        request_id="req-1",
        tool_name="shell",
        args_summary={"command": "echo ok"},
        description="Agent requested to run shell",
    )

    assert event.event == "permission_request"


def test_tool_result_event_carries_error_code_and_metadata():
    tool_result = ToolResultEvent(
        tool_name="bash",
        tool_call_id="call-bash",
        success=False,
        content_preview="Exit code: 1",
        error_code="nonzero_exit",
        metadata={"exit_code": 1, "timed_out": False},
    )

    assert tool_result.error_code == "nonzero_exit"
    assert tool_result.metadata["exit_code"] == 1
