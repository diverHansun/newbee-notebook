"""Docker command construction for sandbox execution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from newbee_notebook.core.sandbox.contracts import SandboxExecutionError, SandboxRequest
from newbee_notebook.core.sandbox.docker_config import DockerRunConfig

_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class DockerCommand:
    argv: tuple[str, ...]
    container_name: str
    workspace_dir: Path
    run_dir: Path


class DockerCommandBuilder:
    """Build a shell-free `docker run` argv from a sandbox request."""

    def __init__(self, config: DockerRunConfig) -> None:
        self._config = config

    def build(
        self,
        request: SandboxRequest,
        *,
        container_name: str,
        run_dir: Path | str,
    ) -> DockerCommand:
        if request.network_enabled:
            raise SandboxExecutionError(
                "network_enabled=True is not supported by the Docker sandbox batch"
            )

        workspace_dir, resolved_run_dir = self._resolve_mounts(request, run_dir)
        argv = self._base_run_argv(
            container_name=container_name,
            workspace_dir=workspace_dir,
            run_dir=resolved_run_dir,
            detached=False,
        )
        _append_request_env(argv, request.env)

        argv.extend([self._config.image, *request.argv])
        return DockerCommand(
            argv=tuple(argv),
            container_name=container_name,
            workspace_dir=workspace_dir,
            run_dir=resolved_run_dir,
        )

    def build_session_start(
        self,
        request: SandboxRequest,
        *,
        container_name: str,
        run_dir: Path | str,
    ) -> DockerCommand:
        """Build `docker run -d ... tail -f /dev/null` for a warm container."""

        if request.network_enabled:
            raise SandboxExecutionError(
                "network_enabled=True is not supported by the Docker sandbox batch"
            )
        workspace_dir, resolved_run_dir = self._resolve_mounts(request, run_dir)
        argv = self._base_run_argv(
            container_name=container_name,
            workspace_dir=workspace_dir,
            run_dir=resolved_run_dir,
            detached=True,
        )
        argv.extend([self._config.image, "tail", "-f", "/dev/null"])
        return DockerCommand(
            argv=tuple(argv),
            container_name=container_name,
            workspace_dir=workspace_dir,
            run_dir=resolved_run_dir,
        )

    def build_session_exec(
        self,
        request: SandboxRequest,
        *,
        container_name: str,
        workspace_dir: Path,
        run_dir: Path,
    ) -> DockerCommand:
        """Build `docker exec` argv for a command inside a warm container."""

        container_cwd = _container_path_for(
            Path(request.cwd).resolve(strict=False),
            workspace_dir,
            self._config.workspace_target,
        )
        argv: list[str] = [
            self._config.docker_bin,
            "exec",
        ]
        if request.stdin is not None:
            argv.append("-i")
        argv.extend(["--workdir", container_cwd])
        argv.extend(["--env", f"NEWBEE_RUN_DIR={self._config.work_target}"])
        _append_request_env(argv, request.env)
        argv.extend([container_name, *request.argv])
        return DockerCommand(
            argv=tuple(argv),
            container_name=container_name,
            workspace_dir=workspace_dir,
            run_dir=run_dir,
        )

    def build_session_stop(self, *, container_name: str) -> DockerCommand:
        argv = (
            self._config.docker_bin,
            "stop",
            "-t",
            "5",
            container_name,
        )
        return DockerCommand(
            argv=argv,
            container_name=container_name,
            workspace_dir=Path(),
            run_dir=Path(),
        )

    def _resolve_mounts(
        self,
        request: SandboxRequest,
        run_dir: Path | str,
    ) -> tuple[Path, Path]:
        workspace_dir = Path(request.cwd).resolve(strict=False)
        if not workspace_dir.exists():
            raise SandboxExecutionError(f"workspace cwd does not exist: {workspace_dir}")

        resolved_run_dir = Path(run_dir).expanduser().resolve(strict=False)
        self._ensure_run_dir_is_allowed(resolved_run_dir)
        resolved_run_dir.mkdir(parents=True, exist_ok=True)
        return workspace_dir, resolved_run_dir

    def _base_run_argv(
        self,
        *,
        container_name: str,
        workspace_dir: Path,
        run_dir: Path,
        detached: bool,
    ) -> list[str]:
        argv: list[str] = [
            self._config.docker_bin,
            "run",
        ]
        if detached:
            argv.append("-d")
        argv.extend([
            "--rm",
            "--name",
            container_name,
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            str(self._config.pids_limit),
            "--cpus",
            self._config.cpus,
            "--memory",
            self._config.memory,
            "--memory-swap",
            self._config.memory_swap,
            "--user",
            self._config.user,
            "--tmpfs",
            self._config.tmpfs,
            "--mount",
            _mount_arg(
                source=workspace_dir,
                target=self._config.workspace_target,
                readonly=True,
            ),
            "--mount",
            _mount_arg(
                source=run_dir,
                target=self._config.work_target,
                readonly=False,
            ),
            "--workdir",
            self._config.workspace_target,
            "--env",
            f"NEWBEE_RUN_DIR={self._config.work_target}",
        ])
        return argv

    def _ensure_run_dir_is_allowed(self, run_dir: Path) -> None:
        allowed_roots = (
            Path(self._config.run_root).resolve(strict=False),
            *self._config.additional_run_roots,
        )
        if any(_is_relative_to(run_dir, root) for root in allowed_roots):
            return
        roots = ", ".join(str(root) for root in allowed_roots)
        raise SandboxExecutionError(
            f"run_dir must be inside Docker sandbox run roots: {roots}"
        )


def _mount_arg(*, source: Path, target: str, readonly: bool) -> str:
    parts = [
        "type=bind",
        f"source={source}",
        f"target={target}",
    ]
    if readonly:
        parts.append("readonly")
    return ",".join(parts)


def _append_request_env(argv: list[str], env: dict | object) -> None:
    for key, value in sorted(dict(env).items()):
        if not _ENV_NAME_RE.match(str(key)):
            raise SandboxExecutionError(f"invalid environment variable name: {key}")
        if key == "HOME":
            continue
        argv.extend(["--env", f"{key}={value}"])
    argv.extend(["--env", "HOME=/tmp"])


def _container_path_for(host_path: Path, host_root: Path, container_root: str) -> str:
    try:
        relative = host_path.relative_to(host_root)
    except ValueError as exc:
        raise SandboxExecutionError(
            f"cwd must be inside Docker session workspace root: {host_root}"
        ) from exc
    suffix = relative.as_posix()
    return container_root if not suffix or suffix == "." else f"{container_root}/{suffix}"


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True
