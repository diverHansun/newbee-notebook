from __future__ import annotations

import asyncio
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from newbee_notebook.core.sandbox import SandboxRequest
from newbee_notebook.core.sandbox import NotebookSandboxWorkspace
from newbee_notebook.core.sandbox.docker_config import DockerRunConfig
from newbee_notebook.core.sandbox.docker_executor import DockerSandboxExecutor
from newbee_notebook.core.sandbox.docker_session import DockerSandboxSessionRegistry

pytestmark = pytest.mark.integration


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _require_docker_image(image: str) -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker CLI is not available")
    daemon = subprocess.run(
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if daemon.returncode != 0:
        pytest.skip(f"docker daemon is not available: {daemon.stderr.strip()}")
    inspected = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if inspected.returncode != 0:
        pytest.skip(f"docker sandbox image is not available: {image}")


def _executor(tmp_path: Path, *, prefix: str | None = None) -> DockerSandboxExecutor:
    image = "newbee-notebook/api:latest"
    _require_docker_image(image)
    return DockerSandboxExecutor(
        config=DockerRunConfig(
            image=image,
            run_root=tmp_path / "runs",
            container_prefix=prefix or f"newbee-sandbox-test-{uuid.uuid4().hex[:8]}",
            timeout_seconds=10,
        )
    )


@pytest.mark.anyio
async def test_docker_sandbox_executes_bash_and_reads_workspace(tmp_path: Path):
    (tmp_path / "note.txt").write_text("hello from workspace", encoding="utf-8")
    executor = _executor(tmp_path)

    result = await executor.execute(
        SandboxRequest(
            argv=("bash", "-lc", "pwd && cat note.txt"),
            cwd=tmp_path,
            timeout_seconds=10,
        )
    )

    assert result.exit_code == 0
    assert "/workspace" in result.stdout
    assert "hello from workspace" in result.stdout
    assert result.error_code is None


@pytest.mark.anyio
async def test_docker_sandbox_network_enabled_can_resolve_public_dns(tmp_path: Path):
    executor = _executor(tmp_path)

    result = await executor.execute(
        SandboxRequest(
            argv=(
                "python",
                "-c",
                "import socket; print(socket.gethostbyname('example.com'))",
            ),
            cwd=tmp_path,
            timeout_seconds=10,
        )
    )

    assert result.exit_code == 0
    assert result.stdout.strip()


@pytest.mark.anyio
async def test_docker_sandbox_network_enabled_cannot_resolve_compose_sibling(tmp_path: Path):
    executor = _executor(tmp_path)

    result = await executor.execute(
        SandboxRequest(
            argv=(
                "python",
                "-c",
                "import socket; socket.gethostbyname('postgres')",
            ),
            cwd=tmp_path,
            timeout_seconds=10,
        )
    )

    assert result.exit_code != 0


@pytest.mark.anyio
async def test_docker_sandbox_network_disabled_uses_no_network(tmp_path: Path):
    executor = _executor(tmp_path)

    result = await executor.execute(
        SandboxRequest(
            argv=(
                "python",
                "-c",
                "import socket; socket.gethostbyname('example.com')",
            ),
            cwd=tmp_path,
            timeout_seconds=10,
            network_enabled=False,
        )
    )

    assert result.exit_code != 0


@pytest.mark.anyio
async def test_docker_sandbox_keeps_workspace_readonly_but_allows_work_dir(tmp_path: Path):
    executor = _executor(tmp_path)
    run_dir = tmp_path / "runs" / "manual-run"
    run_dir.mkdir(parents=True)

    result = await executor.execute(
        SandboxRequest(
            argv=(
                "bash",
                "-lc",
                "echo saved > /work/out.txt; "
                "echo nope > /workspace/out.txt; "
                "status=$?; echo workspace_write_status=$status; exit 0",
            ),
            cwd=tmp_path,
            run_dir=run_dir,
            timeout_seconds=10,
        )
    )

    assert result.exit_code == 0
    assert (run_dir / "out.txt").read_text(encoding="utf-8").strip() == "saved"
    assert not (tmp_path / "out.txt").exists()
    assert "workspace_write_status=" in result.stdout
    assert "Read-only file system" in result.stderr or "Permission denied" in result.stderr


@pytest.mark.anyio
async def test_docker_sandbox_allows_notebook_scoped_work_dir(tmp_path: Path):
    image = "newbee-notebook/api:latest"
    _require_docker_image(image)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    notebook_workspace = NotebookSandboxWorkspace(root=tmp_path / "sandbox-work")
    binding = notebook_workspace.for_notebook("notebook-123")
    executor = DockerSandboxExecutor(
        config=DockerRunConfig(
            image=image,
            run_root=tmp_path / "runs",
            additional_run_roots=(notebook_workspace.root,),
            timeout_seconds=10,
        )
    )

    result = await executor.execute(
        SandboxRequest(
            argv=("bash", "-lc", "echo shared > /work/shared.txt"),
            cwd=workspace,
            run_dir=binding.work_dir,
            timeout_seconds=10,
        )
    )

    assert result.exit_code == 0
    assert (binding.work_dir / "shared.txt").read_text(encoding="utf-8").strip() == "shared"


@pytest.mark.anyio
async def test_docker_sandbox_reuses_notebook_warm_container(tmp_path: Path):
    image = "newbee-notebook/api:latest"
    _require_docker_image(image)
    prefix = f"newbee-sandbox-warm-{uuid.uuid4().hex[:8]}"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    notebook_workspace = NotebookSandboxWorkspace(root=tmp_path / "sandbox-work")
    binding = notebook_workspace.for_notebook("notebook-123")
    config = DockerRunConfig(
        image=image,
        run_root=tmp_path / "runs",
        additional_run_roots=(notebook_workspace.root,),
        container_prefix=prefix,
        timeout_seconds=10,
    )
    registry = DockerSandboxSessionRegistry(config=config)
    executor = DockerSandboxExecutor(config=config, session_registry=registry)
    request_kwargs = {
        "cwd": workspace,
        "run_dir": binding.work_dir,
        "timeout_seconds": 10,
        "sandbox_session_key": "notebook-123",
    }
    container_name = registry.container_name_for("notebook-123")

    try:
        first = await executor.execute(
            SandboxRequest(
                argv=("bash", "-lc", "echo first > /work/shared.txt && hostname"),
                **request_kwargs,
            )
        )
        second = await executor.execute(
            SandboxRequest(
                argv=("bash", "-lc", "cat /work/shared.txt && hostname"),
                **request_kwargs,
            )
        )

        assert first.exit_code == 0
        assert second.exit_code == 0
        assert "first" in second.stdout
        first_hostname = first.stdout.strip().splitlines()[-1]
        second_hostname = second.stdout.strip().splitlines()[-1]
        assert first_hostname == second_hostname
        visible = subprocess.run(
            ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert visible.stdout.strip() == container_name
    finally:
        await registry.stop("notebook-123")


@pytest.mark.anyio
async def test_docker_sandbox_recovers_from_stale_warm_container_name(
    tmp_path: Path,
):
    image = "newbee-notebook/api:latest"
    _require_docker_image(image)
    prefix = f"newbee-sandbox-stale-{uuid.uuid4().hex[:8]}"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    notebook_workspace = NotebookSandboxWorkspace(root=tmp_path / "sandbox-work")
    binding = notebook_workspace.for_notebook("notebook-123")
    config = DockerRunConfig(
        image=image,
        run_root=tmp_path / "runs",
        additional_run_roots=(notebook_workspace.root,),
        container_prefix=prefix,
        timeout_seconds=10,
    )
    registry = DockerSandboxSessionRegistry(config=config)
    executor = DockerSandboxExecutor(config=config, session_registry=registry)
    container_name = registry.container_name_for("notebook-123")
    stale = subprocess.run(
        ["docker", "run", "-d", "--name", container_name, image, "sleep", "60"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert stale.returncode == 0, stale.stderr

    try:
        result = await executor.execute(
            SandboxRequest(
                argv=("bash", "-lc", "echo recovered"),
                cwd=workspace,
                run_dir=binding.work_dir,
                timeout_seconds=10,
                sandbox_session_key="notebook-123",
            )
        )

        assert result.exit_code == 0
        assert "recovered" in result.stdout
    finally:
        await registry.stop("notebook-123")
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )


@pytest.mark.anyio
async def test_docker_sandbox_timeout_removes_container(tmp_path: Path):
    prefix = f"newbee-sandbox-timeout-{uuid.uuid4().hex[:8]}"
    executor = _executor(tmp_path, prefix=prefix)

    result = await executor.execute(
        SandboxRequest(
            argv=("bash", "-lc", "sleep 30"),
            cwd=tmp_path,
            timeout_seconds=1,
        )
    )

    assert result.timed_out is True
    assert result.error_code == "timeout"
    await asyncio.sleep(0.2)
    remaining = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"name={prefix}", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert remaining.returncode == 0
    assert remaining.stdout.strip() == ""
