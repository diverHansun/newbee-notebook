from __future__ import annotations

from pathlib import Path

import pytest

from newbee_notebook.core.sandbox.notebook_workspace import NotebookSandboxWorkspace

pytestmark = pytest.mark.unit


def test_notebook_workspace_returns_stable_work_dir_for_same_notebook(tmp_path: Path):
    manager = NotebookSandboxWorkspace(root=tmp_path / "sandbox-work")

    first = manager.for_notebook("notebook-123")
    second = manager.for_notebook("notebook-123")

    assert first.notebook_id == "notebook-123"
    assert first.slug == second.slug
    assert first.work_dir == second.work_dir
    assert first.work_dir.is_dir()
    assert first.work_dir == (
        tmp_path / "sandbox-work" / "notebooks" / first.slug / "work"
    ).resolve()
    assert first.container_work_dir == "/work"


def test_notebook_workspace_separates_different_notebooks(tmp_path: Path):
    manager = NotebookSandboxWorkspace(root=tmp_path / "sandbox-work")

    first = manager.for_notebook("notebook-a")
    second = manager.for_notebook("notebook-b")

    assert first.slug != second.slug
    assert first.work_dir != second.work_dir


def test_notebook_workspace_rejects_empty_notebook_id(tmp_path: Path):
    manager = NotebookSandboxWorkspace(root=tmp_path / "sandbox-work")

    with pytest.raises(ValueError, match="notebook_id"):
        manager.for_notebook("   ")


def test_notebook_workspace_slug_cannot_escape_root(tmp_path: Path):
    manager = NotebookSandboxWorkspace(root=tmp_path / "sandbox-work")

    workspace = manager.for_notebook("../secret\\..\\notebook")

    notebooks_root = (tmp_path / "sandbox-work" / "notebooks").resolve()
    workspace.work_dir.relative_to(notebooks_root)
    assert workspace.slug not in {".", ".."}
    assert "/" not in workspace.slug
    assert "\\" not in workspace.slug
