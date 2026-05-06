from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest

from newbee_notebook.core.sandbox.docker_config import DockerRunConfig
from newbee_notebook.core.sandbox.docker_executor import DockerSandboxExecutor
from newbee_notebook.core.sandbox.docker_session import DockerSandboxSessionRegistry
from newbee_notebook.core.shell import BackgroundBashTaskManager, ShellEnvironment
from newbee_notebook.core.tools.bash import build_bash_tool
from newbee_notebook.core.tools.bash_tasks import (
    build_bash_task_output_tool,
    build_bash_task_stop_tool,
)
from newbee_notebook.core.tools.filesystem import build_filesystem_tools

pytestmark = pytest.mark.integration


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _require_docker_image(image: str) -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker CLI is not available")
    inspected = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if inspected.returncode != 0:
        pytest.skip(f"docker sandbox image is not available: {image}")


@pytest.mark.anyio
async def test_bash_tool_executes_inside_docker_sandbox(tmp_path: Path):
    image = "newbee-notebook/api:latest"
    _require_docker_image(image)
    sandbox = DockerSandboxExecutor(
        config=DockerRunConfig(
            image=image,
            run_root=tmp_path / "runs",
            container_prefix="newbee-sandbox-tool-test",
        )
    )
    tool = build_bash_tool(
        ShellEnvironment(
            cwd=tmp_path,
            workspace_roots=(tmp_path,),
            timeout_seconds=10,
        ),
        sandbox_executor=sandbox,
    )

    result = await tool.execute({"command": "echo tool-ok && pwd", "timeout_seconds": 10})

    assert result.error is None
    assert "tool-ok" in result.content
    assert "/workspace" in result.content


@pytest.mark.anyio
async def test_bash_tool_reuses_warm_container_with_shared_work_dir(tmp_path: Path):
    image = "newbee-notebook/api:latest"
    _require_docker_image(image)
    workspace = tmp_path / "workspace"
    work_dir = tmp_path / "sandbox-work" / "notebooks" / "nb1" / "work"
    workspace.mkdir(parents=True)
    work_dir.mkdir(parents=True)
    config = DockerRunConfig(
        image=image,
        run_root=tmp_path / "runs",
        additional_run_roots=(tmp_path / "sandbox-work",),
        container_prefix="newbee-sandbox-tool-warm-test",
        timeout_seconds=10,
    )
    registry = DockerSandboxSessionRegistry(config=config)
    sandbox = DockerSandboxExecutor(config=config, session_registry=registry)
    tool = build_bash_tool(
        ShellEnvironment(
            cwd=workspace,
            workspace_roots=(workspace,),
            run_dir=work_dir,
            sandbox_session_key="notebook-123",
            timeout_seconds=10,
        ),
        sandbox_executor=sandbox,
    )

    try:
        first = await tool.execute(
            {"command": "echo persisted > /work/value.txt", "timeout_seconds": 10}
        )
        second = await tool.execute(
            {"command": "cat /work/value.txt", "timeout_seconds": 10}
        )
    finally:
        await registry.stop("notebook-123")

    assert first.error is None
    assert second.error is None
    assert "persisted" in second.content


@pytest.mark.anyio
async def test_bash_and_filesystem_tools_share_notebook_work_view(tmp_path: Path):
    image = "newbee-notebook/api:latest"
    _require_docker_image(image)
    workspace = tmp_path / "workspace"
    work_dir = tmp_path / "sandbox-work" / "notebooks" / "nb-tools" / "work"
    workspace.mkdir(parents=True)
    work_dir.mkdir(parents=True)
    (workspace / "host.md").write_text("host original", encoding="utf-8")
    config = DockerRunConfig(
        image=image,
        run_root=tmp_path / "runs",
        additional_run_roots=(tmp_path / "sandbox-work",),
        container_prefix="newbee-sandbox-tool-fs-test",
        timeout_seconds=10,
    )
    registry = DockerSandboxSessionRegistry(config=config)
    sandbox = DockerSandboxExecutor(config=config, session_registry=registry)
    environment = ShellEnvironment(
        cwd=workspace,
        workspace_roots=(workspace,),
        run_dir=work_dir,
        sandbox_session_key="notebook-fs-tools",
        allow_workspace_write=False,
        timeout_seconds=10,
    )
    bash = build_bash_tool(environment, sandbox_executor=sandbox)
    fs_tools = {tool.name: tool for tool in build_filesystem_tools(environment)}

    try:
        created = await bash.execute(
            {
                "command": "printf 'alpha needle\\n' > /work/from-bash.txt",
                "timeout_seconds": 10,
            }
        )
        read_result = await fs_tools["read_file"].execute(
            {"path": "/work/from-bash.txt", "n_lines": 5}
        )
        grep_result = await fs_tools["grep_files"].execute(
            {"pattern": "needle", "path": "/work", "output_mode": "content"}
        )
        glob_result = await fs_tools["glob_files"].execute(
            {"pattern": "*.txt", "directory": "/work"}
        )
        edit_result = await fs_tools["edit_file"].execute(
            {
                "path": "/work/from-bash.txt",
                "old": "needle",
                "new": "changed",
            }
        )
        write_result = await fs_tools["write_file"].execute(
            {"path": "/work/from-write.txt", "content": "written by fs\n"}
        )
        workspace_write = await fs_tools["write_file"].execute(
            {"path": "/workspace/host.md", "content": "mutated"}
        )
        verify = await bash.execute(
            {
                "command": "cat /work/from-bash.txt /work/from-write.txt",
                "timeout_seconds": 10,
            }
        )
    finally:
        await registry.stop("notebook-fs-tools")

    assert created.error is None
    assert read_result.error is None
    assert "alpha needle" in read_result.content
    assert grep_result.error is None
    assert "needle" in grep_result.content
    assert glob_result.error is None
    assert "/work/from-bash.txt" in glob_result.content
    assert edit_result.error is None
    assert write_result.error is None
    assert workspace_write.error == "outside_workspace"
    assert (workspace / "host.md").read_text(encoding="utf-8") == "host original"
    assert verify.error is None
    assert "alpha changed" in verify.content
    assert "written by fs" in verify.content


@pytest.mark.anyio
async def test_bash_tool_background_task_runs_in_warm_container(tmp_path: Path):
    image = "newbee-notebook/api:latest"
    _require_docker_image(image)
    workspace = tmp_path / "workspace"
    work_dir = tmp_path / "sandbox-work" / "notebooks" / "nb1" / "work"
    workspace.mkdir(parents=True)
    work_dir.mkdir(parents=True)
    config = DockerRunConfig(
        image=image,
        run_root=tmp_path / "runs",
        additional_run_roots=(tmp_path / "sandbox-work",),
        container_prefix="newbee-sandbox-tool-bg-test",
        timeout_seconds=10,
    )
    registry = DockerSandboxSessionRegistry(config=config)
    sandbox = DockerSandboxExecutor(config=config, session_registry=registry)
    environment = ShellEnvironment(
        cwd=workspace,
        workspace_roots=(workspace,),
        run_dir=work_dir,
        sandbox_session_key="notebook-bg",
        allow_workspace_write=False,
        timeout_seconds=10,
    )
    manager = BackgroundBashTaskManager(tasks_root=work_dir / ".tasks")
    bash = build_bash_tool(
        environment,
        sandbox_executor=sandbox,
        background_task_manager=manager,
    )
    output_tool = build_bash_task_output_tool(manager)

    try:
        started = await bash.execute(
            {
                "command": "sleep 1; echo bg-done > /work/bg.txt; echo bg-out",
                "background": True,
                "description": "background e2e",
                "timeout_seconds": 10,
            }
        )
        task_id = started.metadata["task_id"]
        completed = await manager.wait(task_id, timeout_seconds=15)
        output = await output_tool.execute({"task_id": task_id})
        verify = await bash.execute({"command": "cat /work/bg.txt", "timeout_seconds": 10})
    finally:
        await registry.stop("notebook-bg")

    assert started.error is None
    assert completed.status == "completed"
    assert output.error is None
    assert "bg-out" in output.content
    assert verify.error is None
    assert "bg-done" in verify.content


@pytest.mark.anyio
async def test_bash_task_stop_cancels_warm_container_command(tmp_path: Path):
    image = "newbee-notebook/api:latest"
    _require_docker_image(image)
    workspace = tmp_path / "workspace"
    work_dir = tmp_path / "sandbox-work" / "notebooks" / "nb-stop" / "work"
    workspace.mkdir(parents=True)
    work_dir.mkdir(parents=True)
    config = DockerRunConfig(
        image=image,
        run_root=tmp_path / "runs",
        additional_run_roots=(tmp_path / "sandbox-work",),
        container_prefix="newbee-sandbox-tool-bg-stop",
        timeout_seconds=30,
    )
    registry = DockerSandboxSessionRegistry(config=config)
    sandbox = DockerSandboxExecutor(config=config, session_registry=registry)
    environment = ShellEnvironment(
        cwd=workspace,
        workspace_roots=(workspace,),
        run_dir=work_dir,
        sandbox_session_key="notebook-bg-stop",
        allow_workspace_write=False,
        timeout_seconds=30,
    )
    manager = BackgroundBashTaskManager(tasks_root=work_dir / ".tasks")
    bash = build_bash_tool(
        environment,
        sandbox_executor=sandbox,
        background_task_manager=manager,
    )
    stop_tool = build_bash_task_stop_tool(manager)

    started = await bash.execute(
        {
            "command": "sleep 30",
            "background": True,
            "description": "stop e2e",
            "timeout_seconds": 30,
        }
    )
    task_id = started.metadata["task_id"]
    while manager.get(task_id).status != "running":
        await asyncio.sleep(0)
    stopped = await stop_tool.execute({"task_id": task_id})

    assert started.error is None
    assert stopped.error is None
    assert manager.get(task_id).status == "stopped"
