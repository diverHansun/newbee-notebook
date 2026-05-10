from __future__ import annotations

from pathlib import Path

import pytest

from newbee_notebook.core.policy import RiskLevel, ToolClass
from newbee_notebook.core.sandbox import SandboxRequest, SandboxResult
from newbee_notebook.core.shell import BackgroundShellTaskManager, ShellEnvironment
from newbee_notebook.core.tools.shell import build_shell_tool
from newbee_notebook.core.tools.shell_tasks import (
    build_shell_task_list_tool,
    build_shell_task_output_tool,
    build_shell_task_stop_tool,
)

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
async def test_shell_tool_exposes_policy_metadata_and_delegates_to_sandbox(tmp_path: Path):
    sandbox = RecordingSandboxExecutor()
    tool = build_shell_tool(
        ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)),
        sandbox_executor=sandbox,
    )

    result = await tool.execute({"command": "echo hello", "timeout_seconds": 3})

    assert tool.name == "shell"
    assert tool.tool_class == ToolClass.SHELL
    assert tool.risk_level == RiskLevel.DANGEROUS
    assert tool.sandbox_required is True
    assert result.error is None
    assert "Exit code: 0" in result.content
    assert "hello" in result.content
    assert sandbox.requests[0].argv == ("bash", "-lc", "echo hello")
    assert sandbox.requests[0].timeout_seconds == 3


@pytest.mark.anyio
async def test_shell_tool_fails_closed_when_no_sandbox_executor_is_configured(tmp_path: Path):
    tool = build_shell_tool(ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)))

    result = await tool.execute({"command": "echo hello"})

    assert result.error == "sandbox_unavailable"


@pytest.mark.anyio
async def test_shell_tool_starts_background_task_when_manager_is_configured(tmp_path: Path):
    sandbox = RecordingSandboxExecutor()
    manager = BackgroundShellTaskManager(tasks_root=tmp_path / "tasks")
    tool = build_shell_tool(
        ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)),
        sandbox_executor=sandbox,
        background_task_manager=manager,
    )

    result = await tool.execute(
        {
            "command": "echo background",
            "background": True,
            "description": "run in background",
        }
    )

    assert result.error is None
    assert result.metadata["task_id"]
    completed = await manager.wait(result.metadata["task_id"], timeout_seconds=2)
    assert completed.status == "completed"


def test_shell_tool_schema_requires_description_for_background_tasks(tmp_path: Path):
    tool = build_shell_tool(
        ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)),
        sandbox_executor=RecordingSandboxExecutor(),
    )

    assert {
        "if": {
            "properties": {"background": {"const": True}},
            "required": ["background"],
        },
        "then": {"required": ["command", "description"]},
    } in tool.parameters["allOf"]


@pytest.mark.anyio
async def test_shell_task_tools_list_output_and_stop(tmp_path: Path):
    sandbox = RecordingSandboxExecutor()
    manager = BackgroundShellTaskManager(tasks_root=tmp_path / "tasks")
    environment = ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,))
    task = await manager.start(
        command="echo hello",
        description="hello",
        environment=environment,
        sandbox_executor=sandbox,
    )
    await manager.wait(task.task_id, timeout_seconds=2)
    list_tool = build_shell_task_list_tool(manager)
    output_tool = build_shell_task_output_tool(manager)
    stop_tool = build_shell_task_stop_tool(manager)

    listed = await list_tool.execute({})
    output = await output_tool.execute({"task_id": task.task_id})
    stopped = await stop_tool.execute({"task_id": task.task_id})

    assert listed.error is None
    assert task.task_id in listed.content
    assert output.error is None
    assert "hello" in output.content
    assert stopped.error is None
    assert "completed" in stopped.content


@pytest.mark.anyio
async def test_shell_tool_maps_timeout_and_nonzero_exit(tmp_path: Path):
    timeout_tool = build_shell_tool(
        ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)),
        sandbox_executor=RecordingSandboxExecutor(
            SandboxResult(exit_code=None, stdout="partial", timed_out=True)
        ),
    )
    nonzero_tool = build_shell_tool(
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
