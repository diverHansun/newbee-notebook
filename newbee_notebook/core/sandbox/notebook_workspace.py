"""Notebook-scoped writable workspace management for sandbox execution."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

_SAFE_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class NotebookSandboxWorkspaceBinding:
    """Resolved host/container paths for one notebook sandbox workspace."""

    notebook_id: str
    slug: str
    notebook_dir: Path
    work_dir: Path
    container_work_dir: str


class NotebookSandboxWorkspace:
    """Resolve stable notebook-level `/work` directories."""

    def __init__(
        self,
        *,
        root: Path | str,
        container_work_dir: str = "/work",
    ) -> None:
        self._root = Path(root).expanduser().resolve(strict=False)
        self._container_work_dir = _normalize_container_path(container_work_dir)

    @property
    def root(self) -> Path:
        return self._root

    @property
    def notebooks_root(self) -> Path:
        return self._root / "notebooks"

    def for_notebook(self, notebook_id: str) -> NotebookSandboxWorkspaceBinding:
        normalized_id = str(notebook_id or "").strip()
        if not normalized_id:
            raise ValueError("notebook_id is required")

        slug = _slug_for_notebook_id(normalized_id)
        notebook_dir = (self.notebooks_root / slug).resolve(strict=False)
        _ensure_child(notebook_dir, self.notebooks_root)
        work_dir = notebook_dir / "work"
        work_dir.mkdir(parents=True, exist_ok=True)
        return NotebookSandboxWorkspaceBinding(
            notebook_id=normalized_id,
            slug=slug,
            notebook_dir=notebook_dir,
            work_dir=work_dir,
            container_work_dir=self._container_work_dir,
        )


def _slug_for_notebook_id(notebook_id: str) -> str:
    head = _SAFE_SLUG_RE.sub("-", notebook_id).strip(" ._-").lower()
    if not head:
        head = "notebook"
    head = head[:48].strip(" ._-") or "notebook"
    digest = hashlib.sha256(notebook_id.encode("utf-8")).hexdigest()[:12]
    return f"{head}-{digest}"


def _normalize_container_path(value: str) -> str:
    normalized = str(value or "").strip().replace("\\", "/")
    if not normalized:
        raise ValueError("container_work_dir is required")
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized.rstrip("/") or "/"


def _ensure_child(child: Path, parent: Path) -> None:
    resolved_child = child.resolve(strict=False)
    resolved_parent = parent.resolve(strict=False)
    try:
        resolved_child.relative_to(resolved_parent)
    except ValueError as exc:
        raise ValueError("notebook workspace escaped sandbox root") from exc
