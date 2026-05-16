from __future__ import annotations

from pathlib import Path

import pytest

from newbee_notebook.core.shell import ShellEnvironment
from newbee_notebook.core.tools.filesystem import build_read_file_tool

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_read_file_returns_numbered_lines_and_total_count(tmp_path: Path):
    file_path = tmp_path / "brief.md"
    file_path.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    tool = build_read_file_tool(ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)))

    result = await tool.execute({"path": "brief.md", "line_offset": 2, "n_lines": 1})

    assert result.error is None
    assert "     2\tbeta" in result.content
    assert "Total lines in file: 3." in result.content


@pytest.mark.anyio
async def test_read_file_rejects_line_offset_zero(tmp_path: Path):
    (tmp_path / "brief.md").write_text("alpha\n", encoding="utf-8")
    tool = build_read_file_tool(ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)))

    result = await tool.execute({"path": "brief.md", "line_offset": 0})

    assert result.error == "invalid_line_offset"


@pytest.mark.anyio
async def test_read_file_blocks_binary_content(tmp_path: Path):
    (tmp_path / "image.bin").write_bytes(b"\x00\x01\x02")
    tool = build_read_file_tool(ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)))

    result = await tool.execute({"path": "image.bin"})

    assert result.error == "not_text"
