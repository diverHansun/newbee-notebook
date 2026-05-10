"""Shell adapter that turns shell requests into sandbox requests."""

from __future__ import annotations

from newbee_notebook.core.sandbox import (
    SandboxExecutionError,
    SandboxExecutor,
    SandboxRequest,
    SandboxUnavailableError,
    UnavailableSandboxExecutor,
)
from newbee_notebook.core.shell.environment import ShellEnvironment
from newbee_notebook.core.shell.result import ShellExecutionResult


class ShellExecutor:
    def __init__(
        self,
        *,
        environment: ShellEnvironment,
        sandbox_executor: SandboxExecutor | None = None,
    ) -> None:
        self._environment = environment
        self._sandbox_executor = sandbox_executor or UnavailableSandboxExecutor()

    async def execute_shell(
        self,
        command: str,
        *,
        timeout_seconds: float | None = None,
    ) -> ShellExecutionResult:
        normalized_command = str(command or "")
        if not normalized_command.strip():
            return ShellExecutionResult(
                exit_code=None,
                error_code="empty_command",
                stderr="command is required",
            )

        effective_timeout = self._effective_timeout(timeout_seconds)
        request = SandboxRequest(
            argv=("bash", "-lc", normalized_command),
            cwd=self._environment.cwd,
            env=self._environment.env,
            timeout_seconds=effective_timeout,
            max_output_bytes=self._environment.max_output_bytes,
            network_enabled=True,
            run_dir=self._environment.run_dir,
            sandbox_session_key=self._environment.sandbox_session_key,
        )
        try:
            sandbox_result = await self._sandbox_executor.execute(request)
        except SandboxUnavailableError as exc:
            return ShellExecutionResult(
                exit_code=None,
                error_code="sandbox_unavailable",
                stderr=str(exc),
            )
        except SandboxExecutionError as exc:
            return ShellExecutionResult(
                exit_code=None,
                error_code="sandbox_error",
                stderr=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            return ShellExecutionResult(
                exit_code=None,
                error_code="sandbox_error",
                stderr=str(exc),
            )
        return ShellExecutionResult.from_sandbox(sandbox_result)

    async def execute_bash(
        self,
        command: str,
        *,
        timeout_seconds: float | None = None,
    ) -> ShellExecutionResult:
        return await self.execute_shell(command, timeout_seconds=timeout_seconds)

    def _effective_timeout(self, timeout_seconds: float | None) -> float:
        default_timeout = float(self._environment.timeout_seconds)
        if timeout_seconds is None:
            return default_timeout
        try:
            requested = float(timeout_seconds)
        except (TypeError, ValueError):
            return default_timeout
        if requested <= 0:
            return default_timeout
        return min(requested, default_timeout)
