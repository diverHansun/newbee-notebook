"""Implementation of the read_file tool."""

from __future__ import annotations

from typing import Any

from newbee_notebook.core.policy import RiskLevel, ToolClass
from newbee_notebook.core.shell import PathAccessError, PathPolicy, ShellEnvironment
from newbee_notebook.core.tools.contracts import ToolCallResult, ToolDefinition
from newbee_notebook.core.tools.filesystem.common import (
    error_result,
    path_error_result,
    read_text_file,
)

MAX_READ_LINES = 1_000
DEFAULT_READ_LINES = 200
MAX_LINE_LENGTH = 2_000
MAX_READ_BYTES = 256_000


def build_read_file_tool(environment: ShellEnvironment) -> ToolDefinition:
    policy = PathPolicy(environment)

    async def _execute(args: dict[str, Any]) -> ToolCallResult:
        raw_path = args.get("path")
        if raw_path is None or not str(raw_path).strip():
            return error_result("invalid_path", "path is required")

        try:
            line_offset = int(args.get("line_offset", 1))
            n_lines = int(args.get("n_lines", DEFAULT_READ_LINES))
        except (TypeError, ValueError):
            return error_result("invalid_line_range", "line_offset and n_lines must be integers")

        if line_offset == 0:
            return error_result("invalid_line_offset", "line_offset is 1-based; use 1 for the first line")
        if n_lines <= 0:
            return error_result("invalid_line_count", "n_lines must be positive")
        n_lines = min(n_lines, MAX_READ_LINES)

        try:
            path = policy.resolve_read_path(str(raw_path))
        except PathAccessError as exc:
            return path_error_result(exc)

        if not path.exists():
            return error_result("file_not_found", f"File does not exist: {policy.relative_to_cwd(path)}")
        if path.is_dir():
            return error_result("is_directory", f"Path is a directory: {policy.relative_to_cwd(path)}")

        try:
            text, byte_truncated = read_text_file(path, max_bytes=MAX_READ_BYTES)
        except UnicodeDecodeError:
            return error_result("not_text", "Only UTF-8 text files can be read")

        lines = text.splitlines()
        total_lines = len(lines)
        if line_offset > 0:
            start_index = min(line_offset - 1, total_lines)
        else:
            start_index = max(total_lines + line_offset, 0)
        end_index = min(start_index + n_lines, total_lines)

        numbered_lines = []
        line_truncated = False
        for index in range(start_index, end_index):
            line = lines[index]
            if len(line) > MAX_LINE_LENGTH:
                line = f"{line[:MAX_LINE_LENGTH]}... [line truncated]"
                line_truncated = True
            numbered_lines.append(f"{index + 1:6}\t{line}")

        header = f"Total lines in file: {total_lines}."
        if byte_truncated:
            header += " File content was truncated by byte limit."
        if line_truncated:
            header += " Some lines were truncated by length limit."
        content = "\n".join([*numbered_lines, "", header])
        return ToolCallResult(
            content=content,
            metadata={
                "path": policy.relative_to_cwd(path),
                "start_line": start_index + 1 if total_lines else 0,
                "end_line": end_index,
                "total_lines": total_lines,
                "truncated": byte_truncated or line_truncated or end_index < total_lines,
            },
        )

    return ToolDefinition(
        name="read_file",
        description="Read a UTF-8 text file from the current workspace with line numbers.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "line_offset": {"type": "integer", "default": 1},
                "n_lines": {"type": "integer", "default": DEFAULT_READ_LINES},
            },
            "required": ["path"],
        },
        execute=_execute,
        tool_class=ToolClass.READ,
        risk_level=RiskLevel.SAFE,
    )
