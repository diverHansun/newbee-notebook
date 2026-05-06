from __future__ import annotations

from pathlib import Path

import pytest

from newbee_notebook.core.shell import ShellEnvironment
from newbee_notebook.core.tools.filesystem import build_grep_files_tool

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_grep_files_content_mode_returns_line_numbers(tmp_path: Path):
    (tmp_path / "a.md").write_text("alpha\nneedle\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("other\n", encoding="utf-8")
    tool = build_grep_files_tool(ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)))

    result = await tool.execute(
        {
            "pattern": "needle",
            "path": ".",
            "glob": "*.md",
            "output_mode": "content",
        }
    )

    assert result.error is None
    assert result.content == "a.md:2:needle"


@pytest.mark.anyio
async def test_grep_files_filters_sensitive_files(tmp_path: Path):
    (tmp_path / ".env").write_text("TOKEN=needle\n", encoding="utf-8")
    (tmp_path / "a.md").write_text("needle\n", encoding="utf-8")
    tool = build_grep_files_tool(ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)))

    result = await tool.execute({"pattern": "needle", "path": ".", "output_mode": "files_with_matches"})

    assert result.error is None
    assert ".env" not in result.content
    assert "a.md" in result.content
