"""Shell execution result contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from newbee_notebook.core.sandbox import SandboxResult


@dataclass(frozen=True)
class ShellExecutionResult:
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    truncated: bool = False
    error_code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_sandbox(cls, result: SandboxResult) -> "ShellExecutionResult":
        return cls(
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=result.timed_out,
            truncated=result.truncated,
            error_code=result.error_code,
        )
