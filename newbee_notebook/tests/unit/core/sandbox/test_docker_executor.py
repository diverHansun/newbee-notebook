from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from newbee_notebook.core.sandbox import SandboxRequest
from newbee_notebook.core.sandbox.docker_config import DockerRunConfig
from newbee_notebook.core.sandbox.docker_executor import (
    DockerProcessResult,
    DockerSandboxExecutor,
    LimitedOutputBuffer,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend():
    return "asyncio"


class RecordingRunner:
    def __init__(self, result: DockerProcessResult):
        self.result = result
        self.runs: list[tuple[str, ...]] = []
        self.cleanups: list[str] = []

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
        return self.result

    async def cleanup(self, *, docker_bin: str, container_name: str) -> None:
        del docker_bin
        self.cleanups.append(container_name)


class NetworkCreateRunner:
    def __init__(self):
        self.runs: list[tuple[str, ...]] = []
        self.cleanups: list[str] = []

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
        if argv[:3] == ("docker", "network", "inspect"):
            return DockerProcessResult(exit_code=1, stderr="network not found")
        if argv[:3] == ("docker", "network", "create"):
            return DockerProcessResult(exit_code=0, stdout="newbee_skill_net\n")
        return DockerProcessResult(exit_code=0, stdout="hello\n")

    async def cleanup(self, *, docker_bin: str, container_name: str) -> None:
        del docker_bin
        self.cleanups.append(container_name)


class RecordingSessionRegistry:
    def __init__(self, result: DockerProcessResult):
        self.result = result
        self.requests: list[SandboxRequest] = []

    async def execute(self, request: SandboxRequest) -> DockerProcessResult:
        self.requests.append(request)
        return self.result


class BlockingRunner:
    def __init__(self):
        self.started = asyncio.Event()
        self.runs: list[tuple[str, ...]] = []
        self.cleanups: list[str] = []

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
        self.started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async def cleanup(self, *, docker_bin: str, container_name: str) -> None:
        del docker_bin
        self.cleanups.append(container_name)


@pytest.mark.anyio
async def test_docker_executor_creates_default_run_dir_and_returns_result(tmp_path: Path):
    runner = RecordingRunner(
        DockerProcessResult(exit_code=0, stdout="hello\n", stderr="", truncated=False)
    )
    config = DockerRunConfig(
        image="sandbox-image:latest",
        run_root=tmp_path / "runs",
        docker_bin="docker",
    )
    executor = DockerSandboxExecutor(
        config=config,
        runner=runner,
        name_factory=lambda: "newbee-sandbox-test",
    )

    result = await executor.execute(
        SandboxRequest(argv=("bash", "-lc", "echo hello"), cwd=tmp_path)
    )

    assert result.exit_code == 0
    assert result.stdout == "hello\n"
    assert result.error_code is None
    assert runner.cleanups == []
    assert (tmp_path / "runs" / "newbee-sandbox-test").is_dir()
    assert runner.runs[0] == ("docker", "network", "inspect", "newbee_skill_net")
    assert runner.runs[-1][-4:] == ("sandbox-image:latest", "bash", "-lc", "echo hello")


@pytest.mark.anyio
async def test_docker_executor_cleans_container_after_timeout(tmp_path: Path):
    runner = RecordingRunner(
        DockerProcessResult(
            exit_code=None,
            stdout="partial",
            stderr="",
            timed_out=True,
            truncated=False,
        )
    )
    executor = DockerSandboxExecutor(
        config=DockerRunConfig(run_root=tmp_path / "runs"),
        runner=runner,
        name_factory=lambda: "newbee-sandbox-timeout",
    )

    result = await executor.execute(
        SandboxRequest(
            argv=("bash", "-lc", "sleep 99"),
            cwd=tmp_path,
            network_enabled=False,
        )
    )

    assert result.timed_out is True
    assert result.error_code == "timeout"
    assert runner.cleanups == ["newbee-sandbox-timeout"]


@pytest.mark.anyio
async def test_docker_executor_cleans_container_after_cancellation(tmp_path: Path):
    runner = BlockingRunner()
    executor = DockerSandboxExecutor(
        config=DockerRunConfig(run_root=tmp_path / "runs"),
        runner=runner,
        name_factory=lambda: "newbee-sandbox-cancel",
    )

    task = asyncio.create_task(
        executor.execute(
            SandboxRequest(
                argv=("bash", "-lc", "sleep 99"),
                cwd=tmp_path,
                network_enabled=False,
            )
        )
    )
    await runner.started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert runner.cleanups == ["newbee-sandbox-cancel"]


@pytest.mark.anyio
async def test_docker_executor_creates_configured_network_before_networked_run(tmp_path: Path):
    runner = NetworkCreateRunner()
    executor = DockerSandboxExecutor(
        config=DockerRunConfig(run_root=tmp_path / "runs", network_name="newbee_skill_net"),
        runner=runner,
        name_factory=lambda: "newbee-sandbox-network",
    )

    result = await executor.execute(
        SandboxRequest(
            argv=("bash", "-lc", "curl https://example.com"),
            cwd=tmp_path,
            network_enabled=True,
        )
    )

    assert result.exit_code == 0
    assert runner.runs[0] == ("docker", "network", "inspect", "newbee_skill_net")
    assert runner.runs[1] == (
        "docker",
        "network",
        "create",
        "--driver",
        "bridge",
        "--opt",
        "com.docker.network.bridge.enable_icc=false",
        "--label",
        "com.newbee_notebook.role=sandbox",
        "newbee_skill_net",
    )
    assert runner.runs[-1][runner.runs[-1].index("--network") + 1] == "newbee_skill_net"


@pytest.mark.anyio
async def test_docker_executor_routes_session_key_to_warm_registry(tmp_path: Path):
    runner = RecordingRunner(DockerProcessResult(exit_code=0, stdout="unexpected"))
    registry = RecordingSessionRegistry(DockerProcessResult(exit_code=0, stdout="warm\n"))
    executor = DockerSandboxExecutor(
        config=DockerRunConfig(run_root=tmp_path / "runs"),
        runner=runner,
        session_registry=registry,
    )

    result = await executor.execute(
        SandboxRequest(
            argv=("bash", "-lc", "echo warm"),
            cwd=tmp_path,
            run_dir=tmp_path / "runs" / "nb-work",
            sandbox_session_key="notebook-123",
        )
    )

    assert result.stdout == "warm\n"
    assert registry.requests[0].sandbox_session_key == "notebook-123"
    assert runner.runs == []


def test_limited_output_buffer_marks_truncation_without_growing_unbounded():
    buffer = LimitedOutputBuffer(max_bytes=5)

    buffer.append(b"hello")
    buffer.append(b" world")

    assert buffer.text == "hello"
    assert buffer.truncated is True
