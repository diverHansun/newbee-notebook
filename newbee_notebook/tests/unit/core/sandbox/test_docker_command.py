from __future__ import annotations

from pathlib import Path

import pytest

from newbee_notebook.core.sandbox import SandboxExecutionError, SandboxRequest
from newbee_notebook.core.sandbox.docker_command import DockerCommandBuilder
from newbee_notebook.core.sandbox.docker_config import DockerRunConfig

pytestmark = pytest.mark.unit


def _value_after(argv: tuple[str, ...], option: str) -> str:
    index = argv.index(option)
    return argv[index + 1]


def test_docker_command_mounts_workspace_readonly_and_run_dir_writable(tmp_path: Path):
    workspace = tmp_path / "workspace"
    run_root = tmp_path / "runs"
    run_dir = run_root / "newbee-sandbox-test"
    workspace.mkdir()
    run_dir.mkdir(parents=True)
    config = DockerRunConfig(
        image="sandbox-image:latest",
        run_root=run_root,
        docker_bin="docker",
    )
    request = SandboxRequest(
        argv=("bash", "-lc", "echo hi"),
        cwd=workspace,
        env={"A": "1"},
    )

    command = DockerCommandBuilder(config).build(
        request,
        container_name="newbee-sandbox-test",
        run_dir=run_dir,
    )

    assert command.container_name == "newbee-sandbox-test"
    assert command.run_dir == run_dir.resolve()
    assert command.argv[:4] == ("docker", "run", "--rm", "--name")
    assert _value_after(command.argv, "--name") == "newbee-sandbox-test"
    assert _value_after(command.argv, "--network") == "newbee_skill_net"
    assert "--read-only" in command.argv
    assert ("--cap-drop", "ALL") == (
        command.argv[command.argv.index("--cap-drop")],
        command.argv[command.argv.index("--cap-drop") + 1],
    )
    assert ("--security-opt", "no-new-privileges") == (
        command.argv[command.argv.index("--security-opt")],
        command.argv[command.argv.index("--security-opt") + 1],
    )
    assert _value_after(command.argv, "--workdir") == "/workspace"
    assert "--env" in command.argv
    assert "A=1" in command.argv
    assert "HOME=/tmp" in command.argv
    assert "NEWBEE_RUN_DIR=/work" in command.argv
    assert (
        "--mount",
        f"type=bind,source={workspace.resolve()},target=/workspace,readonly",
    ) in zip(command.argv, command.argv[1:], strict=False)
    assert (
        "--mount",
        f"type=bind,source={run_dir.resolve()},target=/work",
    ) in zip(command.argv, command.argv[1:], strict=False)
    assert command.argv[-4:] == ("sandbox-image:latest", "bash", "-lc", "echo hi")


def test_docker_command_can_disable_network_per_request(tmp_path: Path):
    config = DockerRunConfig(run_root=tmp_path / "runs")
    request = SandboxRequest(
        argv=("bash", "-lc", "echo hi"),
        cwd=tmp_path,
        network_enabled=False,
    )

    command = DockerCommandBuilder(config).build(
        request,
        container_name="newbee-sandbox-test",
        run_dir=tmp_path / "runs" / "newbee-sandbox-test",
    )

    assert _value_after(command.argv, "--network") == "none"


def test_docker_command_rejects_run_dir_outside_run_root(tmp_path: Path):
    config = DockerRunConfig(run_root=tmp_path / "runs")
    request = SandboxRequest(argv=("bash", "-lc", "echo hi"), cwd=tmp_path)

    with pytest.raises(SandboxExecutionError, match="run_dir"):
        DockerCommandBuilder(config).build(
            request,
            container_name="newbee-sandbox-test",
            run_dir=tmp_path / "elsewhere",
        )


def test_docker_command_allows_run_dir_inside_additional_run_root(tmp_path: Path):
    workspace = tmp_path / "workspace"
    run_root = tmp_path / "runs"
    notebook_work_root = tmp_path / "sandbox-work"
    run_dir = notebook_work_root / "notebooks" / "nb1" / "work"
    workspace.mkdir()
    config = DockerRunConfig(
        run_root=run_root,
        additional_run_roots=(notebook_work_root,),
    )
    request = SandboxRequest(argv=("bash", "-lc", "echo hi"), cwd=workspace)

    command = DockerCommandBuilder(config).build(
        request,
        container_name="newbee-sandbox-test",
        run_dir=run_dir,
    )

    assert command.run_dir == run_dir.resolve()
