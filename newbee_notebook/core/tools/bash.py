"""Agent-visible bash tool backed by the sandbox contract."""

from __future__ import annotations

from typing import Any

from newbee_notebook.core.policy import RiskLevel, ToolClass
from newbee_notebook.core.sandbox import SandboxExecutor
from newbee_notebook.core.shell import ShellEnvironment, ShellExecutionResult, ShellExecutor
from newbee_notebook.core.tools.contracts import ToolCallResult, ToolDefinition


def build_bash_tool(
    environment: ShellEnvironment,
    *,
    sandbox_executor: SandboxExecutor | None = None,
    shell_executor: ShellExecutor | None = None,
) -> ToolDefinition:
    executor = shell_executor or ShellExecutor(
        environment=environment,
        sandbox_executor=sandbox_executor,
    )

    async def _execute(args: dict[str, Any]) -> ToolCallResult:
        command = str(args.get("command") or "")
        if not command.strip():
            return ToolCallResult(content="command is required", error="empty_command")
        if bool(args.get("background", False)):
            return ToolCallResult(
                content="Background bash execution is not supported in this batch.",
                error="background_not_supported",
            )

        timeout_seconds = args.get("timeout_seconds", args.get("timeout"))
        shell_result = await executor.execute_bash(
            command,
            timeout_seconds=timeout_seconds,
        )
        error = _result_error(shell_result)
        return ToolCallResult(
            content=_format_shell_result(shell_result),
            metadata={
                "exit_code": shell_result.exit_code,
                "timed_out": shell_result.timed_out,
                "truncated": shell_result.truncated,
            },
            error=error,
        )

    return ToolDefinition(
        name="bash",
        description="Run a bash command inside the configured sandbox and return stdout, stderr, and exit code.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout_seconds": {"type": "number", "default": environment.timeout_seconds},
                "background": {"type": "boolean", "default": False},
                "description": {"type": "string"},
            },
            "required": ["command"],
        },
        execute=_execute,
        tool_class=ToolClass.BASH,
        risk_level=RiskLevel.DANGEROUS,
        sandbox_required=True,
    )


def _result_error(result: ShellExecutionResult) -> str | None:
    if result.error_code:
        return result.error_code
    if result.timed_out:
        return "timeout"
    if result.exit_code not in (0, None):
        return "nonzero_exit"
    return None


def _format_shell_result(result: ShellExecutionResult) -> str:
    exit_code = "timeout" if result.timed_out else result.exit_code
    lines = [f"Exit code: {exit_code}"]
    if result.truncated:
        lines.append("Output truncated: true")
    if result.stdout:
        lines.extend(["STDOUT:", result.stdout.rstrip()])
    if result.stderr:
        lines.extend(["STDERR:", result.stderr.rstrip()])
    if not result.stdout and not result.stderr:
        lines.append("(no output)")
    return "\n".join(lines)
