"""Agent-visible tools for background bash tasks."""

from __future__ import annotations

from typing import Any

from newbee_notebook.core.policy import RiskLevel, ToolClass
from newbee_notebook.core.shell import BackgroundBashTaskManager
from newbee_notebook.core.tools.contracts import ToolCallResult, ToolDefinition


def build_bash_task_output_tool(
    manager: BackgroundBashTaskManager,
) -> ToolDefinition:
    async def _execute(args: dict[str, Any]) -> ToolCallResult:
        task_id = str(args.get("task_id") or "").strip()
        if not task_id:
            return ToolCallResult(content="task_id is required", error="invalid_task_id")
        try:
            max_bytes = int(args.get("max_bytes", 16_000))
            output = manager.output(task_id, max_bytes=max(1, max_bytes))
        except KeyError as exc:
            return ToolCallResult(content=str(exc), error="task_not_found")
        return ToolCallResult(
            content=output.content,
            metadata={
                "task_id": output.task_id,
                "status": output.status,
                "log_path": str(output.log_path),
                "truncated": output.truncated,
            },
        )

    return ToolDefinition(
        name="bash_task_output",
        description="Read the output log for a background bash task.",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "max_bytes": {"type": "integer", "default": 16000},
            },
            "required": ["task_id"],
        },
        execute=_execute,
        tool_class=ToolClass.READ,
        risk_level=RiskLevel.SAFE,
    )


def build_bash_task_stop_tool(
    manager: BackgroundBashTaskManager,
) -> ToolDefinition:
    async def _execute(args: dict[str, Any]) -> ToolCallResult:
        task_id = str(args.get("task_id") or "").strip()
        if not task_id:
            return ToolCallResult(content="task_id is required", error="invalid_task_id")
        try:
            record = await manager.stop(task_id)
        except KeyError as exc:
            return ToolCallResult(content=str(exc), error="task_not_found")
        return ToolCallResult(
            content=f"Task {record.task_id} status: {record.status}",
            metadata={"task_id": record.task_id, "status": record.status},
        )

    return ToolDefinition(
        name="bash_task_stop",
        description="Stop a running background bash task.",
        parameters={
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
        execute=_execute,
        tool_class=ToolClass.BASH,
        risk_level=RiskLevel.MODERATE,
        sandbox_required=True,
    )


def build_bash_task_list_tool(
    manager: BackgroundBashTaskManager,
) -> ToolDefinition:
    async def _execute(args: dict[str, Any]) -> ToolCallResult:
        try:
            limit = int(args.get("limit", 20))
        except (TypeError, ValueError):
            return ToolCallResult(content="limit must be an integer", error="invalid_limit")
        records = manager.list_tasks(limit=limit)
        if not records:
            return ToolCallResult(content="No background bash tasks.")
        lines = [
            f"{record.task_id}\t{record.status}\texit={record.exit_code}\t{record.description}"
            for record in records
        ]
        return ToolCallResult(
            content="\n".join(lines),
            metadata={
                "tasks": [
                    {
                        "task_id": record.task_id,
                        "status": record.status,
                        "exit_code": record.exit_code,
                        "description": record.description,
                        "log_path": str(record.log_path),
                    }
                    for record in records
                ]
            },
        )

    return ToolDefinition(
        name="bash_task_list",
        description="List recent background bash tasks.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 20}},
        },
        execute=_execute,
        tool_class=ToolClass.READ,
        risk_level=RiskLevel.SAFE,
    )
