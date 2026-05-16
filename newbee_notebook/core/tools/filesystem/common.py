"""Shared helpers for filesystem tool implementations."""

from __future__ import annotations

import difflib
from pathlib import Path

from newbee_notebook.core.shell import PathAccessError
from newbee_notebook.core.tools.contracts import ToolCallResult

MAX_TEXT_BYTES = 512_000


def error_result(code: str, message: str = "") -> ToolCallResult:
    return ToolCallResult(content=message, error=code)


def path_error_result(exc: PathAccessError) -> ToolCallResult:
    return error_result(exc.code, str(exc))


def read_text_file(path: Path, *, max_bytes: int = MAX_TEXT_BYTES) -> tuple[str, bool]:
    data = path.read_bytes()
    truncated = len(data) > max_bytes
    if truncated:
        data = data[:max_bytes]
    if b"\x00" in data:
        raise UnicodeDecodeError("utf-8", data, 0, 1, "NUL byte detected")
    return data.decode("utf-8"), truncated


def unified_diff(before: str, after: str, *, path: str) -> str:
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    return "\n".join(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )
