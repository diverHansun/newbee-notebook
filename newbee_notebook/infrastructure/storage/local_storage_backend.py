"""Local filesystem storage backend (Bind Mount)."""

import shutil
from datetime import timedelta
from pathlib import Path
from typing import BinaryIO

from .base import StorageBackend


class LocalStorageBackend(StorageBackend):
    """Storage backend backed by the local filesystem.

    Files are stored at ``{base_dir}/{object_key}``.
    """

    def __init__(self, base_dir: str) -> None:
        self._base_dir = Path(base_dir).resolve()
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, object_key: str) -> Path:
        """Resolve object key to a local path with traversal guard."""
        path = (self._base_dir / object_key).resolve()
        try:
            path.relative_to(self._base_dir)
        except ValueError as exc:
            raise ValueError(f"Invalid object key: {object_key}")
        return path

    # ------------------------------------------------------------------ #
    # Write
    # ------------------------------------------------------------------ #

    async def save_file(
        self,
        object_key: str,
        data: BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> str:
        path = self._resolve_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            while chunk := data.read(8192):
                f.write(chunk)
        return object_key

    async def save_from_path(
        self,
        object_key: str,
        local_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        target = self._resolve_path(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, target)
        return object_key

    # ------------------------------------------------------------------ #
    # Read
    # ------------------------------------------------------------------ #

    async def get_file(self, object_key: str) -> bytes:
        path = self._resolve_path(object_key)
        if not path.exists():
            raise FileNotFoundError(f"Object not found: {object_key}")
        return path.read_bytes()

    async def get_text(self, object_key: str, encoding: str = "utf-8") -> str:
        path = self._resolve_path(object_key)
        if not path.exists():
            raise FileNotFoundError(f"Object not found: {object_key}")
        return path.read_text(encoding=encoding)

    async def get_file_url(
        self,
        object_key: str,
        expires: timedelta = timedelta(hours=2),
    ) -> str:
        parts = object_key.split("/", 1)
        if len(parts) < 2:
            raise ValueError(f"Invalid object key format: {object_key}")
        document_id = parts[0]
        rest = parts[1]
        if rest.startswith("assets/"):
            relative = rest[len("assets/"):]
            return f"/api/v1/documents/{document_id}/assets/{relative}"
        return f"/api/v1/documents/{document_id}/download"

    # ------------------------------------------------------------------ #
    # Delete
    # ------------------------------------------------------------------ #

    async def delete_file(self, object_key: str) -> None:
        path = self._resolve_path(object_key)
        if not path.exists():
            raise FileNotFoundError(f"Object not found: {object_key}")
        path.unlink()

    async def delete_prefix(self, prefix: str) -> int:
        path = self._resolve_path(prefix.rstrip("/"))
        if not path.exists():
            return 0
        count = sum(1 for f in path.rglob("*") if f.is_file())
        shutil.rmtree(path)
        return count

    # ------------------------------------------------------------------ #
    # Query
    # ------------------------------------------------------------------ #

    async def list_objects(self, prefix: str) -> list[str]:
        path = self._resolve_path(prefix.rstrip("/"))
        if not path.exists():
            return []
        return [
            str(f.relative_to(self._base_dir)).replace("\\", "/")
            for f in path.rglob("*")
            if f.is_file()
        ]

    async def exists(self, object_key: str) -> bool:
        path = self._resolve_path(object_key)
        return path.exists() and path.is_file()
