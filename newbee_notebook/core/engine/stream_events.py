"""Typed stream events for the batch-2 runtime."""

from __future__ import annotations

from dataclasses import dataclass, field

from newbee_notebook.core.tools.contracts import SourceItem, ToolQualityMeta


@dataclass(frozen=True)
class StartEvent:
    message_id: str
    event: str = "start"


@dataclass(frozen=True)
class WarningEvent:
    code: str
    message: str
    event: str = "warning"


@dataclass(frozen=True)
class PhaseEvent:
    stage: str
    event: str = "phase"


@dataclass(frozen=True)
class IntermediateContentEvent:
    delta: str
    event: str = "intermediate_content"


@dataclass(frozen=True)
class ToolCallEvent:
    tool_name: str
    tool_call_id: str
    tool_input: dict
    event: str = "tool_call"


@dataclass(frozen=True)
class ToolResultEvent:
    tool_name: str
    tool_call_id: str
    success: bool
    content_preview: str
    quality_meta: ToolQualityMeta | None = None
    event: str = "tool_result"


@dataclass(frozen=True)
class ConfirmationRequestEvent:
    request_id: str
    tool_name: str
    args_summary: dict
    description: str
    action_type: str = "confirm"
    target_type: str = "unknown"
    event: str = "confirmation_request"


@dataclass(frozen=True)
class SourceEvent:
    sources: list[SourceItem] = field(default_factory=list)
    event: str = "sources"


@dataclass(frozen=True)
class ContentEvent:
    delta: str
    event: str = "content"


@dataclass(frozen=True)
class DoneEvent:
    event: str = "done"


@dataclass(frozen=True)
class ErrorEvent:
    code: str
    message: str
    retriable: bool
    event: str = "error"
