from __future__ import annotations

from pathlib import Path

import pytest

from newbee_notebook.core.policy import RiskLevel, ToolClass
from newbee_notebook.core.sandbox import SandboxRequest, SandboxResult
from newbee_notebook.core.shell import ShellEnvironment
from newbee_notebook.core.tools.shell import build_shell_tool

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


def test_shell_tool_exposes_shell_name_and_policy_metadata(tmp_path: Path):
    tool = build_shell_tool(ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)))

    assert tool.name == "shell"
    assert tool.tool_class == ToolClass.SHELL
    assert tool.risk_level == RiskLevel.DANGEROUS
    assert tool.sandbox_required is True
    assert "shell command" in tool.description.lower()


@pytest.mark.anyio
async def test_shell_tool_delegates_to_sandbox_with_shell_semantics(tmp_path: Path):
    sandbox = RecordingSandboxExecutor()
    tool = build_shell_tool(
        ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)),
        sandbox_executor=sandbox,
    )

    result = await tool.execute({"command": "echo hello", "timeout_seconds": 3})

    assert result.error is None
    assert "Exit code: 0" in result.content
    assert "hello" in result.content
    assert sandbox.requests[0].argv == ("bash", "-lc", "echo hello")
    assert sandbox.requests[0].timeout_seconds == 3
