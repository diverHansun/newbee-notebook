from __future__ import annotations

from pathlib import Path

import pytest

from newbee_notebook.core.shell import ShellEnvironment
from newbee_notebook.core.tools.filesystem import build_edit_file_tool, build_write_file_tool

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_edit_file_replaces_single_match_and_returns_diff(tmp_path: Path):
    target = tmp_path / "brief.md"
    target.write_text("alpha\nbeta\n", encoding="utf-8")
    tool = build_edit_file_tool(ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)))

    result = await tool.execute({"path": "brief.md", "old": "beta", "new": "gamma"})

    assert result.error is None
    assert target.read_text(encoding="utf-8") == "alpha\ngamma\n"
    assert "-beta" in result.content
    assert "+gamma" in result.content


@pytest.mark.anyio
async def test_edit_file_rejects_multiple_matches_without_replace_all(tmp_path: Path):
    target = tmp_path / "brief.md"
    target.write_text("same\nsame\n", encoding="utf-8")
    tool = build_edit_file_tool(ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)))

    result = await tool.execute({"path": "brief.md", "old": "same", "new": "changed"})

    assert result.error == "multiple_occurrences"
    assert target.read_text(encoding="utf-8") == "same\nsame\n"


@pytest.mark.anyio
async def test_write_file_overwrite_and_append_modes_return_diff(tmp_path: Path):
    target = tmp_path / "brief.md"
    target.write_text("alpha\n", encoding="utf-8")
    tool = build_write_file_tool(ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)))

    overwrite = await tool.execute({"path": "brief.md", "content": "beta\n", "mode": "overwrite"})
    append = await tool.execute({"path": "brief.md", "content": "gamma\n", "mode": "append"})

    assert overwrite.error is None
    assert append.error is None
    assert target.read_text(encoding="utf-8") == "beta\ngamma\n"
    assert "-alpha" in overwrite.content
    assert "+gamma" in append.content
