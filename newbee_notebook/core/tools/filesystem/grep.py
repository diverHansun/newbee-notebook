"""Implementation of the grep_files tool."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any, Iterable

from newbee_notebook.core.policy import RiskLevel, ToolClass
from newbee_notebook.core.shell import PathAccessError, PathPolicy, ShellEnvironment
from newbee_notebook.core.tools.contracts import ToolCallResult, ToolDefinition
from newbee_notebook.core.tools.filesystem.common import (
    error_result,
    path_error_result,
    read_text_file,
)

DEFAULT_HEAD_LIMIT = 250
MAX_HEAD_LIMIT = 1_000
SKIPPED_DIR_NAMES = {".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache"}


def build_grep_files_tool(environment: ShellEnvironment) -> ToolDefinition:
    policy = PathPolicy(environment)

    async def _execute(args: dict[str, Any]) -> ToolCallResult:
        pattern = str(args.get("pattern") or "")
        if not pattern:
            return error_result("invalid_pattern", "pattern is required")
        try:
            flags = re.IGNORECASE if bool(args.get("ignore_case", False)) else 0
            regex = re.compile(pattern, flags)
        except re.error as exc:
            return error_result("invalid_regex", str(exc))

        output_mode = str(args.get("output_mode") or "files_with_matches")
        if output_mode not in {"content", "files_with_matches", "count_matches"}:
            return error_result("invalid_output_mode", "Unsupported grep output_mode")

        raw_path = args.get("path") or "."
        glob_pattern = args.get("glob")
        try:
            head_limit = min(max(int(args.get("head_limit", DEFAULT_HEAD_LIMIT)), 1), MAX_HEAD_LIMIT)
            offset = max(int(args.get("offset", 0)), 0)
        except (TypeError, ValueError):
            return error_result("invalid_limit", "head_limit and offset must be integers")

        try:
            search_path = policy.resolve_read_path(str(raw_path))
        except PathAccessError as exc:
            return path_error_result(exc)
        if not search_path.exists():
            return error_result("path_not_found", f"Path does not exist: {raw_path}")

        results: list[str] = []
        match_counts: list[tuple[str, int]] = []
        for file_path in _iter_candidate_files(search_path):
            try:
                resolved_file_path = policy.resolve_read_path(file_path)
            except PathAccessError:
                continue
            if policy.is_sensitive_path(resolved_file_path):
                continue
            rel_path = policy.relative_to_cwd(resolved_file_path)
            if glob_pattern and not fnmatch.fnmatch(rel_path, str(glob_pattern)):
                continue
            try:
                text, _ = read_text_file(resolved_file_path)
            except UnicodeDecodeError:
                continue

            file_matches = []
            for line_number, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    file_matches.append((line_number, line))
            if not file_matches:
                continue

            if output_mode == "files_with_matches":
                results.append(rel_path)
            elif output_mode == "count_matches":
                match_counts.append((rel_path, len(file_matches)))
            else:
                for line_number, line in file_matches:
                    results.append(f"{rel_path}:{line_number}:{line}")

        if output_mode == "count_matches":
            results = [f"{rel_path}:{count}" for rel_path, count in sorted(match_counts)]
        else:
            results.sort()
        sliced = results[offset : offset + head_limit]
        return ToolCallResult(
            content="\n".join(sliced),
            metadata={
                "match_count": len(results),
                "offset": offset,
                "head_limit": head_limit,
                "truncated": offset + head_limit < len(results),
            },
        )

    return ToolDefinition(
        name="grep_files",
        description="Search UTF-8 text files in the workspace with a regular expression.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string", "default": "."},
                "glob": {"type": "string"},
                "output_mode": {
                    "type": "string",
                    "enum": ["content", "files_with_matches", "count_matches"],
                    "default": "files_with_matches",
                },
                "ignore_case": {"type": "boolean", "default": False},
                "head_limit": {"type": "integer", "default": DEFAULT_HEAD_LIMIT},
                "offset": {"type": "integer", "default": 0},
            },
            "required": ["pattern"],
        },
        execute=_execute,
        tool_class=ToolClass.READ,
        risk_level=RiskLevel.SAFE,
    )


def _iter_candidate_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    for candidate in sorted(path.rglob("*")):
        if candidate.is_dir():
            continue
        if any(part in SKIPPED_DIR_NAMES for part in candidate.parts):
            continue
        yield candidate
