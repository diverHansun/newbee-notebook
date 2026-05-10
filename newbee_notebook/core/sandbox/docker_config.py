"""Docker sandbox runtime configuration."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

_NETWORK_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")
_RESERVED_NETWORK_NAMES = {
    "bridge",
    "host",
    "none",
    "newbee_notebook_network",
}


def _resolve_path(value: Path | str) -> Path:
    return Path(value).expanduser().resolve(strict=False)


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class DockerRunConfig:
    """Host-side Docker settings for one sandbox executor instance."""

    image: str = "newbee-notebook/api:latest"
    docker_bin: str = "docker"
    run_root: Path | str = Path(".tmp/sandbox-runs")
    additional_run_roots: tuple[Path | str, ...] = ()
    container_prefix: str = "newbee-sandbox"
    network_name: str = "newbee_skill_net"
    workspace_target: str = "/workspace"
    work_target: str = "/work"
    timeout_seconds: float = 30.0
    max_output_bytes: int = 120_000
    cpus: str = "1"
    memory: str = "512m"
    memory_swap: str = "512m"
    pids_limit: int = 128
    user: str = "1000:1000"
    tmpfs: str = "/tmp:rw,noexec,nosuid,size=64m"

    def __post_init__(self) -> None:
        image = str(self.image).strip()
        docker_bin = str(self.docker_bin).strip()
        container_prefix = str(self.container_prefix).strip()
        network_name = str(self.network_name).strip()
        if not image:
            raise ValueError("Docker sandbox image is required")
        if not docker_bin:
            raise ValueError("Docker binary path is required")
        if not container_prefix:
            raise ValueError("container_prefix is required")
        if not _NETWORK_NAME_RE.match(network_name):
            raise ValueError("network_name must be a valid Docker network name")
        if network_name.casefold() in _RESERVED_NETWORK_NAMES:
            raise ValueError("network_name must not target Docker builtin or compose networks")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")
        if self.pids_limit <= 0:
            raise ValueError("pids_limit must be positive")

        object.__setattr__(self, "image", image)
        object.__setattr__(self, "docker_bin", docker_bin)
        object.__setattr__(self, "run_root", _resolve_path(self.run_root))
        object.__setattr__(
            self,
            "additional_run_roots",
            _resolve_roots(tuple(self.additional_run_roots)),
        )
        object.__setattr__(self, "container_prefix", container_prefix)
        object.__setattr__(self, "network_name", network_name)
        object.__setattr__(self, "workspace_target", _normalize_container_path(self.workspace_target))
        object.__setattr__(self, "work_target", _normalize_container_path(self.work_target))


def build_docker_run_config_from_env(
    *,
    base_dir: Path | str | None = None,
) -> DockerRunConfig:
    """Build Docker sandbox config from environment variables."""

    root = _resolve_path(base_dir or Path.cwd())
    run_root = os.getenv("NEWBEE_SANDBOX_RUN_ROOT")
    return DockerRunConfig(
        image=_env_str("NEWBEE_SANDBOX_IMAGE", "newbee-notebook/api:latest"),
        docker_bin=_env_str("NEWBEE_SANDBOX_DOCKER_BIN", "docker"),
        run_root=_resolve_path(run_root) if run_root else root / ".tmp" / "sandbox-runs",
        container_prefix=_env_str("NEWBEE_SANDBOX_CONTAINER_PREFIX", "newbee-sandbox"),
        network_name=_env_str("NEWBEE_SANDBOX_NETWORK_NAME", "newbee_skill_net"),
        timeout_seconds=_env_float("NEWBEE_SANDBOX_TIMEOUT_SECONDS", 30.0),
        max_output_bytes=_env_int("NEWBEE_SANDBOX_MAX_OUTPUT_BYTES", 120_000),
        cpus=_env_str("NEWBEE_SANDBOX_CPUS", "1"),
        memory=_env_str("NEWBEE_SANDBOX_MEMORY", "512m"),
        memory_swap=_env_str("NEWBEE_SANDBOX_MEMORY_SWAP", "512m"),
        pids_limit=_env_int("NEWBEE_SANDBOX_PIDS_LIMIT", 128),
        user=_env_str("NEWBEE_SANDBOX_USER", "1000:1000"),
        tmpfs=_env_str("NEWBEE_SANDBOX_TMPFS", "/tmp:rw,noexec,nosuid,size=64m"),
    )


def _normalize_container_path(value: str) -> str:
    normalized = str(value).strip().replace("\\", "/")
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized.rstrip("/") or "/"


def _resolve_roots(values: tuple[Path | str, ...]) -> tuple[Path, ...]:
    roots: list[Path] = []
    seen: set[str] = set()
    for value in values:
        path = _resolve_path(value)
        key = str(path).casefold()
        if key not in seen:
            roots.append(path)
            seen.add(key)
    return tuple(roots)
