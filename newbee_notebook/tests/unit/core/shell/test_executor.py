from __future__ import annotations

from pathlib import Path

import pytest

from newbee_notebook.core.sandbox import SandboxRequest, SandboxResult
from newbee_notebook.core.shell import ShellEnvironment, ShellExecutor

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend():
    return "asyncio"


class RecordingSandboxExecutor:
    def __init__(self, result: SandboxResult | None = None):
        self.requests: list[SandboxRequest] = []
        self.result = result or SandboxResult(exit_code=0, stdout="ok\n")

    async def execute(self, request: SandboxRequest) -> SandboxResult:
        self.requests.append(request)
        return self.result


@pytest.mark.anyio
async def test_shell_executor_translates_shell_command_to_sandbox_request(tmp_path: Path):
    sandbox = RecordingSandboxExecutor()
    environment = ShellEnvironment(
        cwd=tmp_path,
        workspace_roots=(tmp_path,),
        env={"A": "1"},
        sandbox_session_key="notebook-123",
        timeout_seconds=20,
        max_output_bytes=1024,
    )
    executor = ShellExecutor(environment=environment, sandbox_executor=sandbox)

    result = await executor.execute_shell("echo hi", timeout_seconds=5)

    assert result.error_code is None
    assert result.stdout == "ok\n"
    assert len(sandbox.requests) == 1
    request = sandbox.requests[0]
    assert request.argv == ("bash", "-lc", "echo hi")
    assert request.cwd == tmp_path.resolve()
    assert request.env == {"A": "1"}
    assert request.timeout_seconds == 5
    assert request.max_output_bytes == 1024
    assert request.network_enabled is True
    assert request.sandbox_session_key == "notebook-123"


@pytest.mark.anyio
async def test_shell_executor_fails_closed_without_sandbox_executor(tmp_path: Path):
    executor = ShellExecutor(
        environment=ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,))
    )

    result = await executor.execute_shell("echo hi")

    assert result.error_code == "sandbox_unavailable"
    assert result.exit_code is None


@pytest.mark.anyio
async def test_shell_executor_rejects_empty_shell_command(tmp_path: Path):
    sandbox = RecordingSandboxExecutor()
    executor = ShellExecutor(
        environment=ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)),
        sandbox_executor=sandbox,
    )

    result = await executor.execute_shell("   ")

    assert result.error_code == "empty_command"
    assert sandbox.requests == []


@pytest.mark.anyio
async def test_shell_executor_keeps_execute_bash_as_compatibility_wrapper(tmp_path: Path):
    sandbox = RecordingSandboxExecutor()
    executor = ShellExecutor(
        environment=ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)),
        sandbox_executor=sandbox,
    )

    result = await executor.execute_bash("echo hi")

    assert result.error_code is None
    assert sandbox.requests[0].argv == ("bash", "-lc", "echo hi")
