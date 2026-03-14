from pathlib import Path

from newbee_notebook.core.common import project_paths


def test_resolve_project_relative_path_prefers_existing_main_repo_path(tmp_path):
    repo_root = tmp_path / "repo"
    worktree_root = repo_root / ".worktrees" / "batch-2-core"
    anchor = worktree_root / "newbee_notebook" / "core" / "common" / "project_paths.py"
    anchor.parent.mkdir(parents=True, exist_ok=True)
    anchor.write_text("# anchor", encoding="utf-8")

    target = repo_root / "models" / "Qwen3-Embedding-0.6B"
    target.mkdir(parents=True, exist_ok=True)

    resolved = project_paths.resolve_project_relative_path(
        "models/Qwen3-Embedding-0.6B",
        start=anchor,
    )

    assert Path(resolved) == target.resolve()
