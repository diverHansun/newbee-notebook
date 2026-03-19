from __future__ import annotations

import json

import pytest

from newbee_notebook.core.engine.agent_loop import AgentLoop
from newbee_notebook.core.engine.confirmation import ConfirmationGateway
from newbee_notebook.core.engine.mode_config import ModeConfigFactory
from newbee_notebook.core.engine.stream_events import ConfirmationRequestEvent, ContentEvent, ToolResultEvent
from newbee_notebook.core.tools.contracts import ToolCallResult, ToolDefinition


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeLLMClient:
    def __init__(self, *, chat_responses=None, stream_chunks=None):
        self.chat_responses = list(chat_responses or [])
        self.stream_chunks = list(stream_chunks or [])
        self.chat_calls: list[dict] = []

    async def chat(self, **kwargs):
        self.chat_calls.append(kwargs)
        return self.chat_responses.pop(0)

    async def chat_stream(self, **kwargs):
        for chunk in self.stream_chunks:
            yield chunk


def _tool_call(name: str, arguments: dict, tool_call_id: str = "call-1") -> dict:
    return {
        "id": tool_call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def _chat_response(*, tool_calls=None, content=None) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls,
                }
            }
        ]
    }


@pytest.mark.anyio
async def test_confirmation_required_tool_emits_request_and_executes_after_approval():
    gateway = ConfirmationGateway()
    execute_payloads: list[dict] = []

    async def _execute(payload: dict) -> ToolCallResult:
        execute_payloads.append(dict(payload))
        return ToolCallResult(content="updated")

    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(tool_calls=[_tool_call("update_note", {"note_id": "n1", "content": "new"})]),
            _chat_response(content="done"),
        ],
    )
    tool = ToolDefinition(
        name="update_note",
        description="update note",
        parameters={"type": "object", "properties": {"note_id": {"type": "string"}}},
        execute=_execute,
    )
    loop = AgentLoop(
        llm_client=llm,
        tools=[tool],
        mode_config=ModeConfigFactory.build(mode="agent", tools=[tool]),
        confirmation_required=frozenset({"update_note"}),
        confirmation_gateway=gateway,
    )

    events = []
    async for event in loop.stream(message="update", chat_history=[]):
        events.append(event)
        if isinstance(event, ConfirmationRequestEvent):
            assert event.tool_name == "update_note"
            assert event.args_summary == {"note_id": "n1"}
            gateway.resolve(event.request_id, approved=True)

    assert execute_payloads == [{"note_id": "n1", "content": "new"}]
    assert any(isinstance(event, ToolResultEvent) and event.success for event in events)
    assert any(isinstance(event, ContentEvent) and event.delta == "done" for event in events)


@pytest.mark.anyio
async def test_confirmation_rejection_skips_tool_execution_and_returns_follow_up_content():
    gateway = ConfirmationGateway()
    execute_payloads: list[dict] = []

    async def _execute(payload: dict) -> ToolCallResult:
        execute_payloads.append(dict(payload))
        return ToolCallResult(content="should not run")

    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(tool_calls=[_tool_call("delete_note", {"note_id": "n1"})]),
            _chat_response(content="understood"),
        ],
    )
    tool = ToolDefinition(
        name="delete_note",
        description="delete note",
        parameters={"type": "object", "properties": {"note_id": {"type": "string"}}},
        execute=_execute,
    )
    loop = AgentLoop(
        llm_client=llm,
        tools=[tool],
        mode_config=ModeConfigFactory.build(mode="agent", tools=[tool]),
        confirmation_required=frozenset({"delete_note"}),
        confirmation_gateway=gateway,
    )

    content_parts: list[str] = []
    async for event in loop.stream(message="delete", chat_history=[]):
        if isinstance(event, ConfirmationRequestEvent):
            gateway.resolve(event.request_id, approved=False)
        if isinstance(event, ContentEvent):
            content_parts.append(event.delta)

    assert execute_payloads == []
    assert "".join(content_parts) == "understood"
