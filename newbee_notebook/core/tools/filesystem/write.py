"""Implementation of the write_file tool."""

from __future__ import annotations

from typing import Any

from newbee_notebook.core.policy import RiskLevel, ToolClass
from newbee_notebook.core.shell import PathAccessError, PathPolicy, ShellEnvironment
from newbee_notebook.core.tools.contracts import ToolCallResult, ToolDefinition
from newbee_notebook.core.tools.filesystem.common import (
    error_result,
    path_error_result,
    read_text_file,
    unified_diff,
)


def build_write_file_tool(environment: ShellEnvironment) -> ToolDefinition:
    policy = PathPolicy(environment)

    async def _execute(args: dict[str, Any]) -> ToolCallResult:
        raw_path = args.get("path")
        content = args.get("content")
        mode = str(args.get("mode") or "overwrite")
        if raw_path is None or not str(raw_path).strip():
            return error_result("invalid_path", "path is required")
        if content is None:
            return error_result("invalid_content", "content is required")
        if mode not in {"overwrite", "append"}:
            return error_result("invalid_mode", "mode must be overwrite or append")

        try:
            path = policy.resolve_write_path(str(raw_path))
        except PathAccessError as exc:
            return path_error_result(exc)
        if not path.parent.exists():
            return error_result("parent_not_found", f"Parent directory does not exist: {path.parent}")
        if path.exists() and path.is_dir():
            return error_result("is_directory", f"Path is a directory: {policy.relative_to_cwd(path)}")

        before = ""
        if path.exists():
            try:
                before, _ = read_text_file(path)
            except UnicodeDecodeError:
                return error_result("not_text", "Only UTF-8 text files can be overwritten or appended")

        after = str(content) if mode == "overwrite" else f"{before}{content}"
        path.write_text(after, encoding="utf-8", newline="")
        rel_path = policy.relative_to_cwd(path)
        return ToolCallResult(
            content=unified_diff(before, after, path=rel_path),
            metadata={"path": rel_path, "mode": mode},
        )

    return ToolDefinition(
        name="write_file",
        description="Overwrite or append UTF-8 text in a workspace file and return a unified diff.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "mode": {"type": "string", "enum": ["overwrite", "append"], "default": "overwrite"},
            },
            "required": ["path", "content"],
        },
        execute=_execute,
        tool_class=ToolClass.WRITE,
        risk_level=RiskLevel.MODERATE,
    )
