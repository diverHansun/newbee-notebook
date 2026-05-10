from __future__ import annotations

import json

import pytest

from newbee_notebook.core.engine.agent_loop import AgentLoop
from newbee_notebook.core.engine.mode_config import ModeConfigFactory
from newbee_notebook.core.engine.stream_events import ContentEvent, PermissionRequestEvent, ToolResultEvent
from newbee_notebook.core.permission import PermissionRequestGateway
from newbee_notebook.core.policy import (
    AgentPolicy,
    PolicyDecider,
    RiskLevel,
    SkillPolicyContext,
    ToolClass,
)
from newbee_notebook.core.tools.contracts import ToolCallResult, ToolDefinition


@pytest.fixture
def anyio_backend():
    return "asyncio"


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

    async def chat(self, **kwargs):
        self.chat_calls.append(kwargs)
        return self.chat_responses.pop(0)

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


@pytest.mark.anyio
async def test_legacy_bash_tool_call_is_normalized_to_shell():
    execute_payloads: list[dict] = []

    async def _execute(payload: dict) -> ToolCallResult:
        execute_payloads.append(dict(payload))
        return ToolCallResult(content="shell-ok")

    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(tool_calls=[_tool_call("bash", {"command": "echo ok"})]),
            _chat_response(content="done"),
        ],
    )
    tool = ToolDefinition(
        name="shell",
        description="run shell",
        parameters={"type": "object", "properties": {"command": {"type": "string"}}},
        execute=_execute,
        tool_class=ToolClass.SHELL,
        risk_level=RiskLevel.SAFE,
    )
    loop = AgentLoop(
        llm_client=llm,
        tools=[tool],
        mode_config=ModeConfigFactory.build(mode="agent", tools=[tool]),
        policy_decider=PolicyDecider(),
        session_id="s1",
    )

    events = [event async for event in loop.stream(message="run", chat_history=[])]

    assert execute_payloads == [{"command": "echo ok"}]
    assistant_tool_messages = [
        message for message in llm.chat_calls[1]["messages"] if message.get("tool_calls")
    ]
    assert assistant_tool_messages[-1]["tool_calls"][0]["function"]["name"] == "shell"
    assert any(
        isinstance(event, ToolResultEvent)
        and event.tool_name == "shell"
        and event.success
        for event in events
    )


@pytest.mark.anyio
async def test_confirmation_required_tool_emits_request_and_executes_after_approval():
    gateway = PermissionRequestGateway()
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
        if isinstance(event, PermissionRequestEvent):
            assert event.tool_name == "update_note"
            assert event.args_summary == {"note_id": "n1"}
            gateway.resolve(event.request_id, approved=True)

    assert execute_payloads == [{"note_id": "n1", "content": "new"}]
    assert any(isinstance(event, ToolResultEvent) and event.success for event in events)
    assert any(isinstance(event, ContentEvent) and event.delta == "done" for event in events)


@pytest.mark.anyio
async def test_confirmation_rejection_skips_tool_execution_and_returns_follow_up_content():
    gateway = PermissionRequestGateway()
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
        if isinstance(event, PermissionRequestEvent):
            gateway.resolve(event.request_id, approved=False)
        if isinstance(event, ContentEvent):
            content_parts.append(event.delta)

    assert execute_payloads == []
    assert "".join(content_parts) == "understood"


@pytest.mark.anyio
async def test_policy_gate_asks_for_write_tool_even_without_legacy_confirmation_rule():
    gateway = PermissionRequestGateway()
    execute_payloads: list[dict] = []

    async def _execute(payload: dict) -> ToolCallResult:
        execute_payloads.append(dict(payload))
        return ToolCallResult(content="written")

    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(tool_calls=[_tool_call("write_file", {"path": "out.md"})]),
            _chat_response(content="skipped"),
        ],
    )
    tool = ToolDefinition(
        name="write_file",
        description="write file",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}},
        execute=_execute,
        tool_class=ToolClass.WRITE,
        risk_level=RiskLevel.MODERATE,
    )
    loop = AgentLoop(
        llm_client=llm,
        tools=[tool],
        mode_config=ModeConfigFactory.build(mode="agent", tools=[tool]),
        confirmation_gateway=gateway,
        policy_decider=PolicyDecider(),
        session_id="s1",
    )

    events = []
    async for event in loop.stream(message="write", chat_history=[]):
        events.append(event)
        if isinstance(event, PermissionRequestEvent):
            assert event.capability_signature.startswith("global:write_file:")
            assert event.risk_level == RiskLevel.MODERATE
            gateway.resolve(event.request_id, approved=False)

    assert execute_payloads == []
    assert any(
        isinstance(event, ToolResultEvent)
        and event.tool_name == "write_file"
        and not event.success
        for event in events
    )


@pytest.mark.anyio
async def test_policy_gate_yolo_allows_write_tool_without_confirmation():
    execute_payloads: list[dict] = []

    async def _execute(payload: dict) -> ToolCallResult:
        execute_payloads.append(dict(payload))
        return ToolCallResult(content="written")

    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(tool_calls=[_tool_call("write_file", {"path": "out.md"})]),
            _chat_response(content="done"),
        ],
    )
    tool = ToolDefinition(
        name="write_file",
        description="write file",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}},
        execute=_execute,
        tool_class=ToolClass.WRITE,
        risk_level=RiskLevel.MODERATE,
    )
    loop = AgentLoop(
        llm_client=llm,
        tools=[tool],
        mode_config=ModeConfigFactory.build(mode="agent", tools=[tool]),
        policy_decider=PolicyDecider(),
        agent_policy=AgentPolicy.YOLO,
        session_id="s1",
    )

    events = [event async for event in loop.stream(message="write", chat_history=[])]

    assert execute_payloads == [{"path": "out.md"}]
    assert not any(isinstance(event, PermissionRequestEvent) for event in events)


@pytest.mark.anyio
async def test_policy_gate_adds_skill_scope_to_confirmation_signature():
    gateway = PermissionRequestGateway()

    async def _execute(payload: dict) -> ToolCallResult:
        return ToolCallResult(content="written")

    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(tool_calls=[_tool_call("write_file", {"path": "out.md"})]),
            _chat_response(content="skipped"),
        ],
    )
    tool = ToolDefinition(
        name="write_file",
        description="write file",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}},
        execute=_execute,
        tool_class=ToolClass.WRITE,
        risk_level=RiskLevel.MODERATE,
    )
    loop = AgentLoop(
        llm_client=llm,
        tools=[tool],
        mode_config=ModeConfigFactory.build(mode="agent", tools=[tool]),
        confirmation_gateway=gateway,
        policy_decider=PolicyDecider(),
        session_id="s1",
        skill_context=SkillPolicyContext(name="demo", content_hash="hash123"),
    )

    signatures: list[str] = []
    async for event in loop.stream(message="write", chat_history=[]):
        if isinstance(event, PermissionRequestEvent):
            signatures.append(event.capability_signature)
            gateway.resolve(event.request_id, approved=False)

    assert signatures
    assert signatures[0].startswith("skill:demo@hash123:write_file:")


@pytest.mark.anyio
async def test_policy_gate_protects_textual_tool_call_emitted_during_final_synthesis():
    gateway = PermissionRequestGateway()
    write_payloads: list[dict] = []

    async def _read(_: dict) -> ToolCallResult:
        return ToolCallResult(content="evidence")

    async def _write(payload: dict) -> ToolCallResult:
        write_payloads.append(dict(payload))
        return ToolCallResult(content="written")

    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "plan"})]),
            _chat_response(content="after-denial"),
        ],
        stream_chunks=[
            {
                "choices": [
                    {
                        "delta": {
                            "content": (
                                "<tool_call>write_file"
                                "<arg_key>path</arg_key><arg_value>out.md</arg_value>"
                                "</tool_call>"
                            )
                        }
                    }
                ]
            }
        ],
    )
    read_tool = ToolDefinition(
        name="knowledge_base",
        description="read",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}},
        execute=_read,
        tool_class=ToolClass.READ,
        risk_level=RiskLevel.SAFE,
    )
    write_tool = ToolDefinition(
        name="write_file",
        description="write",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}},
        execute=_write,
        tool_class=ToolClass.WRITE,
        risk_level=RiskLevel.MODERATE,
    )
    loop = AgentLoop(
        llm_client=llm,
        tools=[read_tool, write_tool],
        mode_config=ModeConfigFactory.build(mode="agent", tools=[read_tool, write_tool]),
        confirmation_gateway=gateway,
        policy_decider=PolicyDecider(),
        session_id="s1",
    )

    async for event in loop.stream(message="write after read", chat_history=[]):
        if isinstance(event, PermissionRequestEvent):
            assert event.tool_name == "write_file"
            gateway.resolve(event.request_id, approved=False)

    assert write_payloads == []
