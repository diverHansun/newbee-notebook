"""Project path resolution helpers.

These helpers keep path handling stable across the main repository and any
git worktree nested under `.worktrees/`.
"""

from __future__ import annotations

from pathlib import Path


def get_project_root(start: str | Path | None = None) -> Path:
    """Return the nearest repository-like root containing `newbee_notebook/`."""
    anchor = Path(start or __file__).resolve()
    for candidate in [anchor, *anchor.parents]:
        if (candidate / "newbee_notebook").is_dir():
            return candidate
    return anchor.parent


def resolve_project_relative_path(path_value: str, *, start: str | Path | None = None) -> str:
    """Resolve a relative project path against the nearest existing ancestor path."""

    candidate_path = Path(path_value)
    if candidate_path.is_absolute():
        return str(candidate_path)

    anchor = Path(start or __file__).resolve()
    for base in [anchor, *anchor.parents]:
        resolved = (base / candidate_path).resolve()
        if resolved.exists():
            return str(resolved)

    project_root = get_project_root(start=anchor)
    return str((project_root / candidate_path).resolve())


def get_models_directory(start: str | Path | None = None) -> Path:
    """Return the effective models directory path."""
    return Path(resolve_project_relative_path("models", start=start))


def get_configs_directory(start: str | Path | None = None) -> Path:
    """Return the effective repo-level configs directory path."""
    return get_project_root(start=start) / "configs"
