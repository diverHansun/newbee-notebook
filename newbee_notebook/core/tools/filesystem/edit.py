"""Implementation of the edit_file tool."""

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


def build_edit_file_tool(environment: ShellEnvironment) -> ToolDefinition:
    policy = PathPolicy(environment)

    async def _execute(args: dict[str, Any]) -> ToolCallResult:
        raw_path = args.get("path")
        old = args.get("old")
        new = args.get("new")
        replace_all = bool(args.get("replace_all", False))
        if raw_path is None or not str(raw_path).strip():
            return error_result("invalid_path", "path is required")
        if old is None or old == "":
            return error_result("invalid_old", "old must be a non-empty string")
        if new is None:
            return error_result("invalid_new", "new is required")

        try:
            path = policy.resolve_write_path(str(raw_path))
        except PathAccessError as exc:
            return path_error_result(exc)
        if not path.exists():
            return error_result("file_not_found", f"File does not exist: {policy.relative_to_cwd(path)}")
        if path.is_dir():
            return error_result("is_directory", f"Path is a directory: {policy.relative_to_cwd(path)}")

        try:
            before, _ = read_text_file(path)
        except UnicodeDecodeError:
            return error_result("not_text", "Only UTF-8 text files can be edited")

        matched_old, matched_new, count = _find_matching_variant(before, str(old), str(new))
        if count == 0:
            return error_result("no_match", "old string was not found")
        if count > 1 and not replace_all:
            return error_result("multiple_occurrences", "old string appears multiple times; use replace_all")

        after = before.replace(matched_old, matched_new, -1 if replace_all else 1)
        path.write_text(after, encoding="utf-8", newline="")
        rel_path = policy.relative_to_cwd(path)
        return ToolCallResult(
            content=unified_diff(before, after, path=rel_path),
            metadata={"path": rel_path, "replacements": count if replace_all else 1},
        )

    return ToolDefinition(
        name="edit_file",
        description="Replace text in a UTF-8 workspace file and return a unified diff.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old": {"type": "string"},
                "new": {"type": "string"},
                "replace_all": {"type": "boolean", "default": False},
            },
            "required": ["path", "old", "new"],
        },
        execute=_execute,
        tool_class=ToolClass.EDIT,
        risk_level=RiskLevel.MODERATE,
    )


def _find_matching_variant(content: str, old: str, new: str) -> tuple[str, str, int]:
    variants = [(old, new)]
    if "\r\n" in old:
        variants.append((old.replace("\r\n", "\n"), new.replace("\r\n", "\n")))
    elif "\n" in old:
        variants.append((old.replace("\n", "\r\n"), new.replace("\n", "\r\n")))

    seen: set[tuple[str, str]] = set()
    for old_variant, new_variant in variants:
        key = (old_variant, new_variant)
        if key in seen:
            continue
        seen.add(key)
        count = content.count(old_variant)
        if count:
            return old_variant, new_variant, count
    return old, new, 0
