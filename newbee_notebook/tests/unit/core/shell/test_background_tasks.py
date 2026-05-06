from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from newbee_notebook.core.sandbox import SandboxRequest, SandboxResult
from newbee_notebook.core.shell.background_tasks import BackgroundBashTaskManager
from newbee_notebook.core.shell.environment import ShellEnvironment

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeSandboxExecutor:
    def __init__(self):
        self.requests: list[SandboxRequest] = []
        self.block = False
        self.release = asyncio.Event()

    async def execute(self, request: SandboxRequest) -> SandboxResult:
        self.requests.append(request)
        if self.block:
            await self.release.wait()
        return SandboxResult(exit_code=0, stdout="hello from bg\n")


@pytest.mark.anyio
async def test_background_bash_task_completes_and_writes_log(tmp_path: Path):
    sandbox = FakeSandboxExecutor()
    manager = BackgroundBashTaskManager(tasks_root=tmp_path / "tasks")
    environment = ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,))

    task = await manager.start(
        command="echo hello",
        description="say hello",
        environment=environment,
        sandbox_executor=sandbox,
    )
    completed = await manager.wait(task.task_id, timeout_seconds=2)
    output = manager.output(task.task_id)

    assert completed.status == "completed"
    assert completed.exit_code == 0
    assert "hello from bg" in output.content
    assert sandbox.requests[0].argv == ("bash", "-lc", "echo hello")


@pytest.mark.anyio
async def test_background_bash_task_stop_cancels_running_task(tmp_path: Path):
    sandbox = FakeSandboxExecutor()
    sandbox.block = True
    manager = BackgroundBashTaskManager(tasks_root=tmp_path / "tasks")
    environment = ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,))

    task = await manager.start(
        command="sleep 99",
        description="long task",
        environment=environment,
        sandbox_executor=sandbox,
    )
    while manager.get(task.task_id).status != "running":
        await asyncio.sleep(0)
    stopped = await manager.stop(task.task_id)

    assert stopped.status == "stopped"
    assert "stopped by request" in manager.output(task.task_id).content


@pytest.mark.anyio
async def test_background_bash_task_wait_timeout_does_not_cancel_task(tmp_path: Path):
    sandbox = FakeSandboxExecutor()
    sandbox.block = True
    manager = BackgroundBashTaskManager(tasks_root=tmp_path / "tasks")
    environment = ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,))

    task = await manager.start(
        command="sleep 99",
        description="long wait",
        environment=environment,
        sandbox_executor=sandbox,
    )
    while manager.get(task.task_id).status != "running":
        await asyncio.sleep(0)

    still_running = await manager.wait(task.task_id, timeout_seconds=0.01)
    sandbox.release.set()
    completed = await manager.wait(task.task_id, timeout_seconds=2)

    assert still_running.status == "running"
    assert completed.status == "completed"


@pytest.mark.anyio
async def test_background_bash_task_immediate_stop_marks_pending_task_stopped(
    tmp_path: Path,
):
    sandbox = FakeSandboxExecutor()
    manager = BackgroundBashTaskManager(tasks_root=tmp_path / "tasks")
    environment = ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,))

    task = await manager.start(
        command="sleep 99",
        description="stop before scheduling",
        environment=environment,
        sandbox_executor=sandbox,
    )
    stopped = await manager.stop(task.task_id)

    assert stopped.status == "stopped"
    assert "stopped by request" in manager.output(task.task_id).content


def test_background_bash_task_list_returns_recent_tasks(tmp_path: Path):
    manager = BackgroundBashTaskManager(tasks_root=tmp_path / "tasks")
    one = manager._make_record(
        task_id="one",
        command="echo one",
        description="one",
    )
    two = manager._make_record(
        task_id="two",
        command="echo two",
        description="two",
    )
    manager._records["one"] = replace(one, created_at=1)
    manager._records["two"] = replace(two, created_at=2)

    tasks = manager.list_tasks()

    assert [task.task_id for task in tasks] == ["two", "one"]
