"""Agent-visible shell tool backed by the sandbox contract."""

from __future__ import annotations

from typing import Any

from newbee_notebook.core.policy import RiskLevel, ToolClass
from newbee_notebook.core.sandbox import SandboxExecutor
from newbee_notebook.core.shell import (
    BackgroundShellTaskManager,
    ShellEnvironment,
    ShellExecutionResult,
    ShellExecutor,
)
from newbee_notebook.core.tools.contracts import ToolCallResult, ToolDefinition


def build_shell_tool(
    environment: ShellEnvironment,
    *,
    sandbox_executor: SandboxExecutor | None = None,
    shell_executor: ShellExecutor | None = None,
    background_task_manager: BackgroundShellTaskManager | None = None,
) -> ToolDefinition:
    executor = shell_executor or ShellExecutor(
        environment=environment,
        sandbox_executor=sandbox_executor,
    )

    async def _execute(args: dict[str, Any]) -> ToolCallResult:
        command = str(args.get("command") or "")
        if not command.strip():
            return ToolCallResult(content="command is required", error="empty_command")
        timeout_seconds = args.get("timeout_seconds", args.get("timeout"))
        if bool(args.get("background", False)):
            if background_task_manager is None:
                return ToolCallResult(
                    content="Background shell execution is not configured.",
                    error="background_not_configured",
                )
            description = str(args.get("description") or "").strip()
            if not description:
                return ToolCallResult(
                    content="description is required for background shell tasks",
                    error="invalid_description",
                )
            task = await background_task_manager.start(
                command=command,
                description=description,
                environment=environment,
                sandbox_executor=sandbox_executor,
                timeout_seconds=timeout_seconds,
            )
            return ToolCallResult(
                content=(
                    f"Started background shell task {task.task_id}.\n"
                    f"Status: {task.status}\n"
                    f"Log: {task.log_path}"
                ),
                metadata={
                    "task_id": task.task_id,
                    "status": task.status,
                    "log_path": str(task.log_path),
                },
            )

        shell_result = await executor.execute_shell(
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
        name="shell",
        description="Run a shell command inside the configured sandbox and return stdout, stderr, and exit code.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout_seconds": {"type": "number", "default": environment.timeout_seconds},
                "background": {"type": "boolean", "default": False},
                "description": {"type": "string"},
            },
            "required": ["command"],
            "allOf": [
                {
                    "if": {
                        "properties": {"background": {"const": True}},
                        "required": ["background"],
                    },
                    "then": {"required": ["command", "description"]},
                }
            ],
        },
        execute=_execute,
        tool_class=ToolClass.SHELL,
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
