from __future__ import annotations

from pathlib import Path

import pytest

from newbee_notebook.core.policy import RiskLevel, ToolClass
from newbee_notebook.core.sandbox import SandboxRequest, SandboxResult
from newbee_notebook.core.shell import ShellEnvironment
from newbee_notebook.core.tools.bash import build_bash_tool

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend():
    return "asyncio"


class RecordingSandboxExecutor:
    def __init__(self, result: SandboxResult | None = None):
        self.requests: list[SandboxRequest] = []
        self.result = result or SandboxResult(exit_code=0, stdout="hello\n")

    async def execute(self, request: SandboxRequest) -> SandboxResult:
        self.requests.append(request)
        return self.result


@pytest.mark.anyio
async def test_bash_tool_exposes_policy_metadata_and_delegates_to_sandbox(tmp_path: Path):
    sandbox = RecordingSandboxExecutor()
    tool = build_bash_tool(
        ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)),
        sandbox_executor=sandbox,
    )

    result = await tool.execute({"command": "echo hello", "timeout_seconds": 3})

    assert tool.tool_class == ToolClass.BASH
    assert tool.risk_level == RiskLevel.DANGEROUS
    assert tool.sandbox_required is True
    assert result.error is None
    assert "Exit code: 0" in result.content
    assert "hello" in result.content
    assert sandbox.requests[0].argv == ("bash", "-lc", "echo hello")
    assert sandbox.requests[0].timeout_seconds == 3


@pytest.mark.anyio
async def test_bash_tool_fails_closed_when_no_sandbox_executor_is_configured(tmp_path: Path):
    tool = build_bash_tool(ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)))

    result = await tool.execute({"command": "echo hello"})

    assert result.error == "sandbox_unavailable"


@pytest.mark.anyio
async def test_bash_tool_rejects_background_mode_for_first_batch(tmp_path: Path):
    sandbox = RecordingSandboxExecutor()
    tool = build_bash_tool(
        ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)),
        sandbox_executor=sandbox,
    )

    result = await tool.execute({"command": "sleep 5", "background": True})

    assert result.error == "background_not_supported"
    assert sandbox.requests == []


@pytest.mark.anyio
async def test_bash_tool_maps_timeout_and_nonzero_exit(tmp_path: Path):
    timeout_tool = build_bash_tool(
        ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)),
        sandbox_executor=RecordingSandboxExecutor(
            SandboxResult(exit_code=None, stdout="partial", timed_out=True)
        ),
    )
    nonzero_tool = build_bash_tool(
        ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)),
        sandbox_executor=RecordingSandboxExecutor(
            SandboxResult(exit_code=2, stderr="bad command")
        ),
    )

    timeout_result = await timeout_tool.execute({"command": "sleep 99"})
    nonzero_result = await nonzero_tool.execute({"command": "exit 2"})

    assert timeout_result.error == "timeout"
    assert "partial" in timeout_result.content
    assert nonzero_result.error == "nonzero_exit"
    assert "bad command" in nonzero_result.content
