"""Docker command construction for sandbox execution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from newbee_notebook.core.sandbox.contracts import SandboxExecutionError, SandboxRequest
from newbee_notebook.core.sandbox.docker_config import DockerRunConfig

_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_NETWORK_EGRESS_GUARD = r"""
import errno
import os
import socket
import struct
import sys

BLOCKS = (
    ("10.0.0.0", 8),
    ("100.64.0.0", 10),
    ("169.254.0.0", 16),
    ("172.16.0.0", 12),
    ("192.168.0.0", 16),
)
NLMSG_ERROR = 2
RTM_NEWROUTE = 24
NLM_F_REQUEST = 1
NLM_F_ACK = 4
NLM_F_EXCL = 0x200
NLM_F_CREATE = 0x400
RT_TABLE_MAIN = 254
RTPROT_STATIC = 4
RT_SCOPE_UNIVERSE = 0
RTN_BLACKHOLE = 6
RTA_DST = 1

def align(length):
    return (length + 3) & ~3

def attr(kind, payload):
    length = 4 + len(payload)
    return struct.pack("HH", length, kind) + payload + (b"\0" * (align(length) - length))

def add_blackhole(sock, seq, cidr):
    address, prefix = cidr
    payload = struct.pack(
        "BBBBBBBBI",
        socket.AF_INET,
        prefix,
        0,
        0,
        RT_TABLE_MAIN,
        RTPROT_STATIC,
        RT_SCOPE_UNIVERSE,
        RTN_BLACKHOLE,
        0,
    )
    payload += attr(RTA_DST, socket.inet_aton(address))
    header = struct.pack(
        "IHHII",
        16 + len(payload),
        RTM_NEWROUTE,
        NLM_F_REQUEST | NLM_F_ACK | NLM_F_CREATE | NLM_F_EXCL,
        seq,
        0,
    )
    sock.send(header + payload)
    data = sock.recv(65535)
    message_type = struct.unpack_from("H", data, 4)[0]
    if message_type != NLMSG_ERROR:
        return
    error = struct.unpack_from("i", data, 16)[0]
    if error not in (0, -errno.EEXIST):
        raise OSError(-error, os.strerror(-error))

sock = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, socket.NETLINK_ROUTE)
for index, block in enumerate(BLOCKS, start=1):
    add_blackhole(sock, index, block)
user = sys.argv[1]
cmd = sys.argv[2:]
if not cmd:
    raise SystemExit("missing sandbox command")
uid, _, gid = user.partition(":")
gid = gid or uid
os.execvp(
    "setpriv",
    [
        "setpriv",
        "--reuid",
        uid,
        "--regid",
        gid,
        "--clear-groups",
        "--bounding-set=-all",
        "--inh-caps=-all",
        "--ambient-caps=-all",
        "--",
        *cmd,
    ],
)
""".strip()


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
        workspace_dir, resolved_run_dir = self._resolve_mounts(request, run_dir)
        argv = self._base_run_argv(
            request=request,
            container_name=container_name,
            workspace_dir=workspace_dir,
            run_dir=resolved_run_dir,
            detached=False,
        )
        _append_request_env(argv, request.env)

        _append_image_and_request_argv(argv, self._config, request)
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

        workspace_dir, resolved_run_dir = self._resolve_mounts(request, run_dir)
        argv = self._base_run_argv(
            request=request,
            container_name=container_name,
            workspace_dir=workspace_dir,
            run_dir=resolved_run_dir,
            detached=True,
        )
        start_request = SandboxRequest(
            argv=("tail", "-f", "/dev/null"),
            cwd=request.cwd,
            env=request.env,
            timeout_seconds=request.timeout_seconds,
            max_output_bytes=request.max_output_bytes,
            network_enabled=request.network_enabled,
            run_dir=request.run_dir,
            stdin=request.stdin,
            sandbox_session_key=request.sandbox_session_key,
        )
        _append_image_and_request_argv(argv, self._config, start_request)
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
        argv.extend(["--user", self._config.user])
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
        request: SandboxRequest,
        container_name: str,
        workspace_dir: Path,
        run_dir: Path,
        detached: bool,
    ) -> list[str]:
        network_name = self._config.network_name if request.network_enabled else "none"
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
            network_name,
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
        ])
        if request.network_enabled:
            argv.extend(["--cap-add", "NET_ADMIN"])
            argv.extend(["--cap-add", "SETUID"])
            argv.extend(["--cap-add", "SETGID"])
            argv.extend(["--cap-add", "SETPCAP"])
        argv.extend([
            "--pids-limit",
            str(self._config.pids_limit),
            "--cpus",
            self._config.cpus,
            "--memory",
            self._config.memory,
            "--memory-swap",
            self._config.memory_swap,
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
        if not request.network_enabled:
            argv.extend(["--user", self._config.user])
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


def _append_image_and_request_argv(
    argv: list[str],
    config: DockerRunConfig,
    request: SandboxRequest,
) -> None:
    if request.network_enabled:
        argv.extend(
            [
                config.image,
                "python",
                "-c",
                _NETWORK_EGRESS_GUARD,
                config.user,
                *request.argv,
            ]
        )
        return
    argv.extend([config.image, *request.argv])


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
