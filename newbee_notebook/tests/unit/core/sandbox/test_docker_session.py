from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from newbee_notebook.core.sandbox import SandboxRequest
from newbee_notebook.core.sandbox import SandboxExecutionError, SandboxUnavailableError
from newbee_notebook.core.sandbox.docker_config import DockerRunConfig
from newbee_notebook.core.sandbox.docker_executor import DockerProcessResult
from newbee_notebook.core.sandbox.docker_session import DockerSandboxSessionRegistry

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend():
    return "asyncio"


class RecordingRunner:
    def __init__(self):
        self.runs: list[tuple[str, ...]] = []

    async def run(
        self,
        argv: tuple[str, ...],
        *,
        stdin: str | None,
        timeout_seconds: float,
        max_output_bytes: int,
    ) -> DockerProcessResult:
        del stdin, timeout_seconds, max_output_bytes
        self.runs.append(argv)
        if argv[:2] == ("docker", "run"):
            return DockerProcessResult(exit_code=0, stdout="container-id\n")
        return DockerProcessResult(exit_code=0, stdout="ok\n")

    async def cleanup(self, *, docker_bin: str, container_name: str) -> None:
        del docker_bin
        self.runs.append(("cleanup", container_name))


class SlowStartRunner(RecordingRunner):
    async def run(
        self,
        argv: tuple[str, ...],
        *,
        stdin: str | None,
        timeout_seconds: float,
        max_output_bytes: int,
    ) -> DockerProcessResult:
        if argv[:2] == ("docker", "run"):
            await asyncio.sleep(0.01)
        return await super().run(
            argv,
            stdin=stdin,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
        )


class BlockingExecRunner(RecordingRunner):
    def __init__(self):
        super().__init__()
        self.exec_started = asyncio.Event()
        self.release_exec = asyncio.Event()
        self.block_exec = False

    async def run(
        self,
        argv: tuple[str, ...],
        *,
        stdin: str | None,
        timeout_seconds: float,
        max_output_bytes: int,
    ) -> DockerProcessResult:
        if argv[:2] == ("docker", "exec") and self.block_exec:
            self.runs.append(argv)
            self.exec_started.set()
            await self.release_exec.wait()
            return DockerProcessResult(exit_code=0, stdout="ok\n")
        return await super().run(
            argv,
            stdin=stdin,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
        )


class BlockingStartRunner(RecordingRunner):
    def __init__(self):
        super().__init__()
        self.start_started = asyncio.Event()

    async def run(
        self,
        argv: tuple[str, ...],
        *,
        stdin: str | None,
        timeout_seconds: float,
        max_output_bytes: int,
    ) -> DockerProcessResult:
        if argv[:2] == ("docker", "run"):
            self.runs.append(argv)
            self.start_started.set()
            await asyncio.Event().wait()
        return await super().run(
            argv,
            stdin=stdin,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
        )


class TimeoutStartRunner(RecordingRunner):
    async def run(
        self,
        argv: tuple[str, ...],
        *,
        stdin: str | None,
        timeout_seconds: float,
        max_output_bytes: int,
    ) -> DockerProcessResult:
        del stdin, timeout_seconds, max_output_bytes
        self.runs.append(argv)
        if argv[:2] == ("docker", "run"):
            return DockerProcessResult(
                exit_code=None,
                timed_out=True,
                error_code="timeout",
            )
        return DockerProcessResult(exit_code=0, stdout="ok\n")


@pytest.mark.anyio
async def test_session_registry_starts_once_and_reuses_container(tmp_path: Path):
    workspace = tmp_path / "workspace"
    work_dir = tmp_path / "work"
    workspace.mkdir()
    work_dir.mkdir()
    runner = RecordingRunner()
    registry = DockerSandboxSessionRegistry(
        config=DockerRunConfig(
            image="sandbox-image:latest",
            run_root=tmp_path / "runs",
            additional_run_roots=(tmp_path,),
            container_prefix="newbee-session-test",
        ),
        runner=runner,
    )
    request = SandboxRequest(
        argv=("bash", "-lc", "echo ok"),
        cwd=workspace,
        run_dir=work_dir,
        sandbox_session_key="notebook-123",
    )

    first = await registry.execute(request)
    second = await registry.execute(request)

    assert first.exit_code == 0
    assert second.exit_code == 0
    run_commands = [argv for argv in runner.runs if argv[:2] == ("docker", "run")]
    exec_commands = [argv for argv in runner.runs if argv[:2] == ("docker", "exec")]
    assert len(run_commands) == 1
    assert len(exec_commands) == 2
    assert registry.container_name_for("notebook-123") in exec_commands[0]


@pytest.mark.anyio
async def test_session_registry_stop_removes_active_session(tmp_path: Path):
    workspace = tmp_path / "workspace"
    work_dir = tmp_path / "work"
    workspace.mkdir()
    work_dir.mkdir()
    runner = RecordingRunner()
    registry = DockerSandboxSessionRegistry(
        config=DockerRunConfig(
            run_root=tmp_path / "runs",
            additional_run_roots=(tmp_path,),
            container_prefix="newbee-session-test",
        ),
        runner=runner,
    )
    request = SandboxRequest(
        argv=("bash", "-lc", "echo ok"),
        cwd=workspace,
        run_dir=work_dir,
        sandbox_session_key="notebook-123",
    )

    await registry.execute(request)
    await registry.stop("notebook-123")

    assert registry.get_active_session("notebook-123") is None
    assert any(argv[:3] == ("docker", "stop", "-t") for argv in runner.runs)


@pytest.mark.anyio
async def test_session_registry_reaps_idle_sessions(tmp_path: Path):
    workspace = tmp_path / "workspace"
    work_dir = tmp_path / "work"
    workspace.mkdir()
    work_dir.mkdir()
    runner = RecordingRunner()
    registry = DockerSandboxSessionRegistry(
        config=DockerRunConfig(
            run_root=tmp_path / "runs",
            additional_run_roots=(tmp_path,),
            container_prefix="newbee-session-test",
        ),
        runner=runner,
        idle_ttl_seconds=5,
        clock=lambda: 100.0,
    )
    request = SandboxRequest(
        argv=("bash", "-lc", "echo ok"),
        cwd=workspace,
        run_dir=work_dir,
        sandbox_session_key="notebook-123",
    )

    await registry.execute(request)
    stopped = await registry.reap_idle(now=106.0)

    assert stopped == ["notebook-123"]
    assert registry.get_active_session("notebook-123") is None


@pytest.mark.anyio
async def test_session_registry_does_not_reap_inflight_session(tmp_path: Path):
    workspace = tmp_path / "workspace"
    work_dir = tmp_path / "work"
    workspace.mkdir()
    work_dir.mkdir()
    runner = BlockingExecRunner()
    registry = DockerSandboxSessionRegistry(
        config=DockerRunConfig(
            run_root=tmp_path / "runs",
            additional_run_roots=(tmp_path,),
            container_prefix="newbee-session-test",
        ),
        runner=runner,
        idle_ttl_seconds=5,
        clock=lambda: 100.0,
    )
    request = SandboxRequest(
        argv=("bash", "-lc", "echo ok"),
        cwd=workspace,
        run_dir=work_dir,
        sandbox_session_key="notebook-123",
    )
    await registry.execute(
        SandboxRequest(
            argv=("bash", "-lc", "echo warmup"),
            cwd=workspace,
            run_dir=work_dir,
            sandbox_session_key="notebook-123",
        )
    )

    runner.block_exec = True
    task = asyncio.create_task(registry.execute(request))
    await runner.exec_started.wait()
    stopped = await registry.reap_idle(now=1000.0)
    runner.release_exec.set()
    await task

    assert stopped == []
    assert registry.get_active_session("notebook-123") is not None
    assert not any(argv[:2] == ("docker", "stop") for argv in runner.runs)


@pytest.mark.anyio
async def test_session_registry_cleans_container_after_cancelled_startup(tmp_path: Path):
    workspace = tmp_path / "workspace"
    work_dir = tmp_path / "work"
    workspace.mkdir()
    work_dir.mkdir()
    runner = BlockingStartRunner()
    registry = DockerSandboxSessionRegistry(
        config=DockerRunConfig(
            run_root=tmp_path / "runs",
            additional_run_roots=(tmp_path,),
            container_prefix="newbee-session-test",
        ),
        runner=runner,
    )
    request = SandboxRequest(
        argv=("bash", "-lc", "echo ok"),
        cwd=workspace,
        run_dir=work_dir,
        sandbox_session_key="notebook-123",
    )

    task = asyncio.create_task(registry.execute(request))
    await runner.start_started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert registry.get_active_session("notebook-123") is None
    assert ("cleanup", registry.container_name_for("notebook-123")) in runner.runs


@pytest.mark.anyio
async def test_session_registry_cleans_container_after_startup_timeout(tmp_path: Path):
    workspace = tmp_path / "workspace"
    work_dir = tmp_path / "work"
    workspace.mkdir()
    work_dir.mkdir()
    runner = TimeoutStartRunner()
    registry = DockerSandboxSessionRegistry(
        config=DockerRunConfig(
            run_root=tmp_path / "runs",
            additional_run_roots=(tmp_path,),
            container_prefix="newbee-session-test",
        ),
        runner=runner,
    )
    request = SandboxRequest(
        argv=("bash", "-lc", "echo ok"),
        cwd=workspace,
        run_dir=work_dir,
        sandbox_session_key="notebook-123",
    )

    with pytest.raises(SandboxExecutionError):
        await registry.execute(request)

    assert registry.get_active_session("notebook-123") is None
    assert ("cleanup", registry.container_name_for("notebook-123")) in runner.runs


@pytest.mark.anyio
async def test_session_registry_serializes_same_key_startup(tmp_path: Path):
    workspace = tmp_path / "workspace"
    work_dir = tmp_path / "work"
    workspace.mkdir()
    work_dir.mkdir()
    runner = SlowStartRunner()
    registry = DockerSandboxSessionRegistry(
        config=DockerRunConfig(
            run_root=tmp_path / "runs",
            additional_run_roots=(tmp_path,),
            container_prefix="newbee-session-test",
        ),
        runner=runner,
    )
    request = SandboxRequest(
        argv=("bash", "-lc", "echo ok"),
        cwd=workspace,
        run_dir=work_dir,
        sandbox_session_key="notebook-123",
    )

    await asyncio.gather(registry.execute(request), registry.execute(request))

    run_commands = [argv for argv in runner.runs if argv[:2] == ("docker", "run")]
    exec_commands = [argv for argv in runner.runs if argv[:2] == ("docker", "exec")]
    assert len(run_commands) == 1
    assert len(exec_commands) == 2


@pytest.mark.anyio
async def test_session_registry_maps_docker_daemon_start_failure_to_unavailable(
    tmp_path: Path,
):
    workspace = tmp_path / "workspace"
    work_dir = tmp_path / "work"
    workspace.mkdir()
    work_dir.mkdir()

    class UnavailableRunner(RecordingRunner):
        async def run(self, argv: tuple[str, ...], **kwargs) -> DockerProcessResult:
            del kwargs
            self.runs.append(argv)
            return DockerProcessResult(
                exit_code=125,
                stderr="Cannot connect to the Docker daemon",
            )

    registry = DockerSandboxSessionRegistry(
        config=DockerRunConfig(
            run_root=tmp_path / "runs",
            additional_run_roots=(tmp_path,),
        ),
        runner=UnavailableRunner(),
    )
    request = SandboxRequest(
        argv=("bash", "-lc", "echo ok"),
        cwd=workspace,
        run_dir=work_dir,
        sandbox_session_key="notebook-123",
    )

    with pytest.raises(SandboxUnavailableError):
        await registry.execute(request)


@pytest.mark.anyio
async def test_session_registry_raises_execution_error_for_start_failure(
    tmp_path: Path,
):
    workspace = tmp_path / "workspace"
    work_dir = tmp_path / "work"
    workspace.mkdir()
    work_dir.mkdir()

    class FailingRunner(RecordingRunner):
        async def run(self, argv: tuple[str, ...], **kwargs) -> DockerProcessResult:
            del kwargs
            self.runs.append(argv)
            return DockerProcessResult(exit_code=1, stderr="image missing")

    registry = DockerSandboxSessionRegistry(
        config=DockerRunConfig(
            run_root=tmp_path / "runs",
            additional_run_roots=(tmp_path,),
        ),
        runner=FailingRunner(),
    )
    request = SandboxRequest(
        argv=("bash", "-lc", "echo ok"),
        cwd=workspace,
        run_dir=work_dir,
        sandbox_session_key="notebook-123",
    )

    with pytest.raises(SandboxExecutionError, match="image missing"):
        await registry.execute(request)
