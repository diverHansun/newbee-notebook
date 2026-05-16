"""Contracts for sandbox-backed command execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class SandboxExecutionError(Exception):
    """Raised when a configured sandbox fails before producing a command result."""


class SandboxUnavailableError(SandboxExecutionError):
    """Raised when no sandbox backend is configured."""


@dataclass(frozen=True)
class SandboxRequest:
    """A sandbox command request expressed as argv, never a host shell string."""

    argv: Sequence[str]
    cwd: Path | str
    env: Mapping[str, object] = field(default_factory=dict)
    timeout_seconds: float = 30.0
    max_output_bytes: int = 120_000
    network_enabled: bool = True
    run_dir: Path | str | None = None
    stdin: str | None = None
    sandbox_session_key: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.argv, str):
            raise ValueError("argv must be a sequence of command arguments")
        argv = tuple(str(item) for item in self.argv)
        if not argv or any(not item for item in argv):
            raise ValueError("argv must contain at least one non-empty argument")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")

        object.__setattr__(self, "argv", argv)
        object.__setattr__(self, "cwd", Path(self.cwd).expanduser().resolve(strict=False))
        object.__setattr__(
            self,
            "env",
            {str(key): str(value) for key, value in dict(self.env).items()},
        )
        object.__setattr__(
            self,
            "run_dir",
            Path(self.run_dir).expanduser().resolve(strict=False)
            if self.run_dir is not None
            else None,
        )
        key = str(self.sandbox_session_key or "").strip()
        object.__setattr__(self, "sandbox_session_key", key or None)


@dataclass(frozen=True)
class SandboxResult:
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    truncated: bool = False
    error_code: str | None = None


class SandboxExecutor(Protocol):
    async def execute(self, request: SandboxRequest) -> SandboxResult:
        """Execute a command request in a configured sandbox."""
