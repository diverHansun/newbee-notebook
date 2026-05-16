"""Implementation of the glob_files tool."""

from __future__ import annotations

from typing import Any

from newbee_notebook.core.policy import RiskLevel, ToolClass
from newbee_notebook.core.shell import PathAccessError, PathPolicy, ShellEnvironment
from newbee_notebook.core.tools.contracts import ToolCallResult, ToolDefinition
from newbee_notebook.core.tools.filesystem.common import error_result, path_error_result

MAX_GLOB_MATCHES = 1_000


def build_glob_files_tool(environment: ShellEnvironment) -> ToolDefinition:
    policy = PathPolicy(environment)

    async def _execute(args: dict[str, Any]) -> ToolCallResult:
        pattern = str(args.get("pattern") or "").strip()
        if not pattern:
            return error_result("invalid_pattern", "pattern is required")
        if pattern.startswith("**"):
            return error_result("unsafe_pattern", "Top-level recursive glob patterns are too broad")

        raw_directory = args.get("directory") or "."
        include_dirs = bool(args.get("include_dirs", False))

        try:
            directory = policy.resolve_read_path(str(raw_directory))
        except PathAccessError as exc:
            return path_error_result(exc)
        if not directory.exists():
            return error_result("directory_not_found", f"Directory does not exist: {raw_directory}")
        if not directory.is_dir():
            return error_result("not_directory", f"Path is not a directory: {raw_directory}")

        matches = []
        for match in directory.glob(pattern):
            try:
                resolved_match = policy.resolve_read_path(match)
            except PathAccessError:
                continue
            if policy.is_sensitive_path(resolved_match):
                continue
            if resolved_match.is_dir() and not include_dirs:
                continue
            matches.append(policy.relative_to_cwd(resolved_match))
            if len(matches) >= MAX_GLOB_MATCHES:
                break
        matches.sort()
        return ToolCallResult(
            content="\n".join(matches),
            metadata={"match_count": len(matches), "truncated": len(matches) >= MAX_GLOB_MATCHES},
        )

    return ToolDefinition(
        name="glob_files",
        description="Find files in the current workspace using a bounded glob pattern.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "directory": {"type": "string", "default": "."},
                "include_dirs": {"type": "boolean", "default": False},
            },
            "required": ["pattern"],
        },
        execute=_execute,
        tool_class=ToolClass.READ,
        risk_level=RiskLevel.SAFE,
    )
