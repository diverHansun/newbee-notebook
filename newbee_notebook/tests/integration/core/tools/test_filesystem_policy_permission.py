from __future__ import annotations

import json
from pathlib import Path

import pytest

from newbee_notebook.core.engine.agent_loop import AgentLoop
from newbee_notebook.core.engine.mode_config import ModeConfigFactory
from newbee_notebook.core.engine.stream_events import ToolResultEvent
from newbee_notebook.core.permission import PermissionRequest, PermissionResponse
from newbee_notebook.core.policy import PolicyDecider
from newbee_notebook.core.shell import ShellEnvironment
from newbee_notebook.core.tools.filesystem import build_filesystem_tools

pytestmark = pytest.mark.integration


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeLLMClient:
    def __init__(self, *, chat_responses=None):
        self.chat_responses = list(chat_responses or [])
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
        self.chat_calls.append(kwargs)
        chunks = self._response_to_stream_batch(self.chat_responses.pop(0))
        for chunk in chunks:
            yield chunk


class _StaticPermissionGateway:
    def __init__(self, response: PermissionResponse):
        self.response = response
        self.requests: list[PermissionRequest] = []

    async def check(self, request: PermissionRequest) -> PermissionResponse:
        self.requests.append(request)
        return self.response


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


def _filesystem_tools(tmp_path: Path):
    workspace = tmp_path / "workspace"
    work_dir = tmp_path / "sandbox-work" / "notebooks" / "nb1" / "work"
    workspace.mkdir(parents=True)
    work_dir.mkdir(parents=True)
    environment = ShellEnvironment(
        cwd=workspace,
        workspace_roots=(workspace,),
        run_dir=work_dir,
        sandbox_session_key="notebook-1",
        allow_workspace_write=False,
    )
    return workspace, work_dir, build_filesystem_tools(environment)


def _filesystem_tools_with_work_under_workspace(tmp_path: Path):
    workspace = tmp_path / "workspace"
    work_dir = workspace / ".tmp" / "sandbox-work" / "notebooks" / "nb1" / "work"
    workspace.mkdir(parents=True)
    work_dir.mkdir(parents=True)
    environment = ShellEnvironment(
        cwd=workspace,
        workspace_roots=(workspace,),
        run_dir=work_dir,
        sandbox_session_key="notebook-1",
        allow_workspace_write=False,
    )
    return workspace, work_dir, build_filesystem_tools(environment)


@pytest.mark.anyio
async def test_read_file_is_allowed_without_permission_check(tmp_path: Path):
    workspace, _, tools = _filesystem_tools(tmp_path)
    (workspace / "existing.md").write_text("safe read\n", encoding="utf-8")
    permission_gateway = _StaticPermissionGateway(PermissionResponse.deny(reason="unexpected"))
    loop = AgentLoop(
        llm_client=_FakeLLMClient(
            chat_responses=[
                _chat_response(
                    tool_calls=[
                        _tool_call(
                            "read_file",
                            {"path": "/workspace/existing.md", "n_lines": 5},
                        )
                    ]
                ),
                _chat_response(content="done"),
            ],
        ),
        tools=tools,
        mode_config=ModeConfigFactory.build(mode="agent", tools=tools),
        policy_decider=PolicyDecider(),
        permission_gateway=permission_gateway,
        session_id="session-1",
    )

    events = [event async for event in loop.stream(message="read", chat_history=[])]

    assert permission_gateway.requests == []
    assert any(
        isinstance(event, ToolResultEvent)
        and event.tool_name == "read_file"
        and event.success
        and "safe read" in event.content_preview
        for event in events
    )


@pytest.mark.anyio
async def test_write_file_denied_by_permission_does_not_touch_work_dir(tmp_path: Path):
    _, work_dir, tools = _filesystem_tools(tmp_path)
    permission_gateway = _StaticPermissionGateway(
        PermissionResponse.deny(reason="permission_denied")
    )
    loop = AgentLoop(
        llm_client=_FakeLLMClient(
            chat_responses=[
                _chat_response(
                    tool_calls=[
                        _tool_call(
                            "write_file",
                            {"path": "/work/out.md", "content": "blocked"},
                        )
                    ]
                ),
                _chat_response(content="denied"),
            ],
        ),
        tools=tools,
        mode_config=ModeConfigFactory.build(mode="agent", tools=tools),
        policy_decider=PolicyDecider(),
        permission_gateway=permission_gateway,
        session_id="session-1",
    )

    events = [event async for event in loop.stream(message="write", chat_history=[])]

    assert len(permission_gateway.requests) == 1
    assert not (work_dir / "out.md").exists()
    assert any(
        isinstance(event, ToolResultEvent)
        and event.tool_name == "write_file"
        and not event.success
        for event in events
    )


@pytest.mark.anyio
async def test_write_file_permission_allow_can_only_modify_work_dir(tmp_path: Path):
    workspace, work_dir, tools = _filesystem_tools(tmp_path)
    (workspace / "host.md").write_text("host original", encoding="utf-8")
    permission_gateway = _StaticPermissionGateway(PermissionResponse.allow(reason="test"))
    loop = AgentLoop(
        llm_client=_FakeLLMClient(
            chat_responses=[
                _chat_response(
                    tool_calls=[
                        _tool_call(
                            "write_file",
                            {"path": "/work/out.md", "content": "allowed"},
                            tool_call_id="call-work",
                        ),
                        _tool_call(
                            "write_file",
                            {"path": "/workspace/host.md", "content": "mutated"},
                            tool_call_id="call-host",
                        ),
                    ]
                ),
                _chat_response(content="done"),
            ],
        ),
        tools=tools,
        mode_config=ModeConfigFactory.build(mode="agent", tools=tools),
        policy_decider=PolicyDecider(),
        permission_gateway=permission_gateway,
        session_id="session-1",
    )

    events = [event async for event in loop.stream(message="write", chat_history=[])]

    assert (work_dir / "out.md").read_text(encoding="utf-8") == "allowed"
    assert (workspace / "host.md").read_text(encoding="utf-8") == "host original"
    write_results = [
        event
        for event in events
        if isinstance(event, ToolResultEvent) and event.tool_name == "write_file"
    ]
    assert [event.success for event in write_results] == [True, False]


@pytest.mark.anyio
async def test_permission_allow_cannot_write_work_dir_through_workspace_alias(
    tmp_path: Path,
):
    _, work_dir, tools = _filesystem_tools_with_work_under_workspace(tmp_path)
    permission_gateway = _StaticPermissionGateway(PermissionResponse.allow(reason="test"))
    loop = AgentLoop(
        llm_client=_FakeLLMClient(
            chat_responses=[
                _chat_response(
                    tool_calls=[
                        _tool_call(
                            "write_file",
                            {
                                "path": "/workspace/.tmp/sandbox-work/notebooks/nb1/work/out.md",
                                "content": "alias",
                            },
                            tool_call_id="call-alias",
                        ),
                        _tool_call(
                            "write_file",
                            {"path": "/work/out.md", "content": "work"},
                            tool_call_id="call-work",
                        ),
                    ]
                ),
                _chat_response(content="done"),
            ],
        ),
        tools=tools,
        mode_config=ModeConfigFactory.build(mode="agent", tools=tools),
        policy_decider=PolicyDecider(),
        permission_gateway=permission_gateway,
        session_id="session-1",
    )

    events = [event async for event in loop.stream(message="write", chat_history=[])]

    assert (work_dir / "out.md").read_text(encoding="utf-8") == "work"
    write_results = [
        event
        for event in events
        if isinstance(event, ToolResultEvent) and event.tool_name == "write_file"
    ]
    assert [event.success for event in write_results] == [False, True]
