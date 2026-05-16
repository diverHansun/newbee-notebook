"""Deterministic tree hashing for installed skill directories."""

from __future__ import annotations

import hashlib
from pathlib import Path


class ContentHasher:
    def calculate(self, skill_dir: str | Path) -> str:
        root = Path(skill_dir)
        if not root.is_dir():
            raise ValueError(f"skill directory does not exist: {root}")

        tree_hash = hashlib.sha256()
        for file_path in sorted(path for path in root.rglob("*") if path.is_file()):
            rel_path = file_path.relative_to(root).as_posix()
            file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
            tree_hash.update(rel_path.encode("utf-8"))
            tree_hash.update(b"\0")
            tree_hash.update(file_hash.encode("ascii"))
            tree_hash.update(b"\0")
        return tree_hash.hexdigest()
