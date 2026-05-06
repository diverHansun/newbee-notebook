from __future__ import annotations

from pathlib import Path

import pytest

from newbee_notebook.core.shell import ShellEnvironment
from newbee_notebook.core.tools.filesystem import build_glob_files_tool

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_glob_files_returns_sorted_relative_matches(tmp_path: Path):
    (tmp_path / "b.py").write_text("", encoding="utf-8")
    (tmp_path / "a.py").write_text("", encoding="utf-8")
    (tmp_path / "notes.md").write_text("", encoding="utf-8")
    tool = build_glob_files_tool(ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)))

    result = await tool.execute({"pattern": "*.py"})

    assert result.error is None
    assert result.content.splitlines() == ["a.py", "b.py"]


@pytest.mark.anyio
async def test_glob_files_rejects_top_level_recursive_pattern(tmp_path: Path):
    tool = build_glob_files_tool(ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)))

    result = await tool.execute({"pattern": "**/*.py"})

    assert result.error == "unsafe_pattern"


@pytest.mark.anyio
async def test_glob_files_does_not_return_matches_outside_workspace(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (tmp_path / "outside.py").write_text("", encoding="utf-8")
    tool = build_glob_files_tool(ShellEnvironment(cwd=workspace, workspace_roots=(workspace,)))

    result = await tool.execute({"pattern": "../*.py"})

    assert result.error is None
    assert result.content == ""
