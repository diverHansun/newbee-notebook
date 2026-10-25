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
    assert ("--cap-drop", "ALL") in zip(command.argv, command.argv[1:], strict=False)
    assert ("--cap-add", "NET_ADMIN") in zip(command.argv, command.argv[1:], strict=False)
    assert ("--cap-add", "SETUID") in zip(command.argv, command.argv[1:], strict=False)
    assert ("--cap-add", "SETGID") in zip(command.argv, command.argv[1:], strict=False)
    assert ("--cap-add", "SETPCAP") in zip(command.argv, command.argv[1:], strict=False)
    assert ("--user", "1000:1000") not in zip(command.argv, command.argv[1:], strict=False)
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
    image_index = command.argv.index("sandbox-image:latest")
    assert command.argv[image_index + 1 : image_index + 3] == ("python", "-c")
    assert command.argv[-4:] == ("1000:1000", "bash", "-lc", "echo hi")


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
    assert ("--cap-add", "NET_ADMIN") not in zip(command.argv, command.argv[1:], strict=False)
    assert ("--user", "1000:1000") in zip(command.argv, command.argv[1:], strict=False)
    assert command.argv[-4:] == ("newbee-notebook/api:latest", "bash", "-lc", "echo hi")


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


@pytest.mark.parametrize("warm", [False, True])
def test_container_backend_mounts_only_skills_and_work_from_docker_host(tmp_path, warm):
    project = tmp_path / "app"
    (project / "configs" / "skills").mkdir(parents=True)
    run_dir = project / "data" / "sandbox" / "nb1"
    config = DockerRunConfig(
        project_root=project,
        host_project_root="/Users/test/My Project",
        workspace_target=str(project),
        run_root=project / "data" / "sandbox",
    )
    builder = DockerCommandBuilder(config)
    build = builder.build_session_start if warm else builder.build
    command = build(
        SandboxRequest(argv=("bash", "-lc", "printf ok"), cwd=project),
        container_name="sandbox-test", run_dir=run_dir,
    )
    mounts = [command.argv[i + 1] for i, v in enumerate(command.argv) if v == "--mount"]
    assert mounts == [
        f"type=bind,source=/Users/test/My Project/configs/skills,target={project}/configs/skills,readonly",
        "type=bind,source=/Users/test/My Project/data/sandbox/nb1,target=/work",
    ]
    assert "docker.sock" not in " ".join(command.argv)
    assert "--read-only" in command.argv
    assert command.workspace_dir == project


def test_container_backend_rejects_work_mount_outside_project(tmp_path):
    project = tmp_path / "app"
    project.mkdir()
    config = DockerRunConfig(
        project_root=project, host_project_root="/Users/test/project",
        run_root=tmp_path / "outside",
    )
    with pytest.raises(SandboxExecutionError, match="project"):
        DockerCommandBuilder(config).build(
            SandboxRequest(argv=("true",), cwd=project),
            container_name="sandbox-test", run_dir=tmp_path / "outside" / "run",
        )
