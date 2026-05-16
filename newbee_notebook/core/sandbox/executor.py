"""Sandbox executor implementations."""

from __future__ import annotations

from newbee_notebook.core.sandbox.contracts import (
    SandboxRequest,
    SandboxResult,
    SandboxUnavailableError,
)


class UnavailableSandboxExecutor:
    """Fail-closed placeholder until a real sandbox backend is configured."""

    async def execute(self, request: SandboxRequest) -> SandboxResult:
        raise SandboxUnavailableError("No sandbox executor is configured")
