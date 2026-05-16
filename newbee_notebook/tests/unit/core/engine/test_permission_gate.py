from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from newbee_notebook.core.engine.agent_loop import AgentLoop
from newbee_notebook.core.engine.mode_config import ModeConfigFactory
from newbee_notebook.core.engine.stream_events import PermissionRequestEvent, ToolResultEvent
from newbee_notebook.core.permission import (
    PermissionChoice,
    PermissionRequest,
    PermissionResponse,
    PermissionResponseKind,
)
from newbee_notebook.core.policy import PolicyDecider, RiskLevel, ToolClass
from newbee_notebook.core.tools.contracts import ToolCallResult, ToolDefinition


class _FakeLLMClient:
    def __init__(self, *, chat_responses=None, stream_chunks=None):
        self.chat_responses = list(chat_responses or [])
        self.stream_chunks = list(stream_chunks or [])
        self.chat_calls: list[dict] = []

    @staticmethod
    def _response_to_stream_batch(response: dict) -> list[dict]:
        message = (response.get("choices") or [{}])[0].get("message") or {}
        delta: dict[str, object] = {}
        if message.get("content"):
            delta["content"] = message.get("content")
        if message.get("tool_calls"):
            delta["tool_calls"] = [
                {"index": index, **tool_call}
                for index, tool_call in enumerate(message["tool_calls"])
            ]
        if not delta:
            return []
        return [{"choices": [{"delta": delta}]}]

    async def chat_stream(self, **kwargs):
        is_reasoning_call = kwargs.get("tools") is not None or kwargs.get("tool_choice") is not None
        if is_reasoning_call and self.chat_responses:
            self.chat_calls.append(kwargs)
            chunks = self._response_to_stream_batch(self.chat_responses.pop(0))
        else:
            chunks = list(self.stream_chunks)
            self.stream_chunks = []
        for chunk in chunks:
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


@dataclass
class _PermissionCall:
    method: str
    request: PermissionRequest | None = None
    choice: object | None = None


class _AllowingPermissionGateway:
    def __init__(self):
        self.calls: list[_PermissionCall] = []

    async def check(self, request: PermissionRequest) -> PermissionResponse:
        self.calls.append(_PermissionCall("check", request=request))
        return PermissionResponse.allow(reason="session_allow")


class _PromptingPermissionGateway:
    def __init__(self):
        self.calls: list[_PermissionCall] = []
        self.created: list[str] = []

    async def check(self, request: PermissionRequest) -> PermissionResponse:
        self.calls.append(_PermissionCall("check", request=request))
        return PermissionResponse.needs_confirmation()

    def create_request(self, request_id: str) -> bool:
        self.created.append(request_id)
        return True

    async def wait_for_choice(self, request_id: str, timeout: float = 180.0):
        return PermissionChoice.ALWAYS_SESSION

    async def record_choice(self, request: PermissionRequest, choice: object) -> PermissionResponse:
        self.calls.append(_PermissionCall("record_choice", request=request, choice=choice))
        return PermissionResponse.allow(reason="always_session")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_policy_ask_uses_permission_allow_without_emitting_permission_request():
    execute_payloads: list[dict] = []

    async def _execute(payload: dict) -> ToolCallResult:
        execute_payloads.append(dict(payload))
        return ToolCallResult(content="written")

    tool = ToolDefinition(
        name="write_file",
        description="write",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}},
        execute=_execute,
        tool_class=ToolClass.WRITE,
        risk_level=RiskLevel.MODERATE,
    )
    permission_gateway = _AllowingPermissionGateway()
    loop = AgentLoop(
        llm_client=_FakeLLMClient(
            chat_responses=[
                _chat_response(tool_calls=[_tool_call("write_file", {"path": "out.md"})]),
                _chat_response(content="done"),
            ],
        ),
        tools=[tool],
        mode_config=ModeConfigFactory.build(mode="agent", tools=[tool]),
        policy_decider=PolicyDecider(),
        permission_gateway=permission_gateway,
        session_id="session-1",
    )

    events = [event async for event in loop.stream(message="write", chat_history=[])]

    assert execute_payloads == [{"path": "out.md"}]
    assert not any(isinstance(event, PermissionRequestEvent) for event in events)
    assert permission_gateway.calls[0].request is not None
    assert permission_gateway.calls[0].request.capability_signature.startswith("global:write_file:")


@pytest.mark.anyio
async def test_policy_ask_records_permission_choice_after_permission_request_event():
    execute_payloads: list[dict] = []

    async def _execute(payload: dict) -> ToolCallResult:
        execute_payloads.append(dict(payload))
        return ToolCallResult(content="written")

    tool = ToolDefinition(
        name="write_file",
        description="write",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}},
        execute=_execute,
        tool_class=ToolClass.WRITE,
        risk_level=RiskLevel.MODERATE,
    )
    permission_gateway = _PromptingPermissionGateway()
    loop = AgentLoop(
        llm_client=_FakeLLMClient(
            chat_responses=[
                _chat_response(tool_calls=[_tool_call("write_file", {"path": "out.md"})]),
                _chat_response(content="done"),
            ],
        ),
        tools=[tool],
        mode_config=ModeConfigFactory.build(mode="agent", tools=[tool]),
        policy_decider=PolicyDecider(),
        permission_gateway=permission_gateway,
        session_id="session-1",
    )

    events = [event async for event in loop.stream(message="write", chat_history=[])]

    permission_events = [event for event in events if isinstance(event, PermissionRequestEvent)]
    assert len(permission_events) == 1
    assert permission_events[0].event == "permission_request"
    assert permission_events[0].response_options == [
        "once",
        "always_session",
        "always_persist",
        "reject",
    ]
    assert execute_payloads == [{"path": "out.md"}]
    assert [call.method for call in permission_gateway.calls] == ["check", "record_choice"]
    assert permission_gateway.calls[-1].choice is PermissionChoice.ALWAYS_SESSION


@pytest.mark.anyio
async def test_permission_rejection_skips_tool_execution():
    class _RejectingPermissionGateway(_AllowingPermissionGateway):
        async def check(self, request: PermissionRequest) -> PermissionResponse:
            self.calls.append(_PermissionCall("check", request=request))
            return PermissionResponse.deny(reason="permission_denied")

    execute_payloads: list[dict] = []

    async def _execute(payload: dict) -> ToolCallResult:
        execute_payloads.append(dict(payload))
        return ToolCallResult(content="should not run")

    tool = ToolDefinition(
        name="write_file",
        description="write",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}},
        execute=_execute,
        tool_class=ToolClass.WRITE,
        risk_level=RiskLevel.MODERATE,
    )
    loop = AgentLoop(
        llm_client=_FakeLLMClient(
            chat_responses=[
                _chat_response(tool_calls=[_tool_call("write_file", {"path": "out.md"})]),
                _chat_response(content="denied"),
            ],
        ),
        tools=[tool],
        mode_config=ModeConfigFactory.build(mode="agent", tools=[tool]),
        policy_decider=PolicyDecider(),
        permission_gateway=_RejectingPermissionGateway(),
        session_id="session-1",
    )

    events = [event async for event in loop.stream(message="write", chat_history=[])]

    assert execute_payloads == []
    assert any(
        isinstance(event, ToolResultEvent)
        and event.tool_name == "write_file"
        and not event.success
        for event in events
    )
