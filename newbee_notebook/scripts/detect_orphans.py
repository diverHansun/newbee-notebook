"""Detect orphan document directories not referenced in database records."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable, List

from newbee_notebook.domain.repositories.document_repository import DocumentRepository
from newbee_notebook.infrastructure.storage.base import StorageBackend
from newbee_notebook.infrastructure.storage.local_storage_backend import LocalStorageBackend

logger = logging.getLogger(__name__)

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _iter_document_dirs(documents_dir: Path) -> Iterable[Path]:
    if not documents_dir.exists() or not documents_dir.is_dir():
        return []
    return [p for p in documents_dir.iterdir() if p.is_dir() and UUID_PATTERN.match(p.name)]


async def _iter_document_ids_from_storage(storage_backend: StorageBackend) -> list[str]:
    keys = await storage_backend.list_objects("")
    document_ids = set()
    for key in keys:
        if "/" not in key:
            continue
        prefix = key.split("/", 1)[0]
        if UUID_PATTERN.match(prefix):
            document_ids.add(prefix)
    return sorted(document_ids)


def _dir_size_bytes(path: Path) -> int:
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total


async def detect_orphan_documents(
    documents_dir: str,
    document_repo: DocumentRepository,
    storage_backend: StorageBackend | None = None,
) -> List[str]:
    """Return orphan document IDs that exist in storage but not in database."""
    root = Path(documents_dir)

    if storage_backend is None or isinstance(storage_backend, LocalStorageBackend):
        fs_dirs = list(_iter_document_dirs(root))
        if not fs_dirs:
            return []
        storage_ids = [d.name for d in fs_dirs]
    else:
        storage_ids = await _iter_document_ids_from_storage(storage_backend)
        if not storage_ids:
            return []

    db_docs = await document_repo.get_batch(storage_ids)
    db_ids = {doc.document_id for doc in db_docs}

    orphan_ids = [doc_id for doc_id in storage_ids if doc_id not in db_ids]
    if not orphan_ids:
        return []

    preview = ", ".join(orphan_ids[:5]) + ("..." if len(orphan_ids) > 5 else "")
    if storage_backend is None or isinstance(storage_backend, LocalStorageBackend):
        total_size = sum(_dir_size_bytes(root / oid) for oid in orphan_ids)
        size_mb = total_size / (1024 * 1024)
        logger.warning(
            "Detected %d orphan document directories (%.1f MB). IDs: %s",
            len(orphan_ids),
            size_mb,
            preview,
        )
    else:
        logger.warning(
            "Detected %d orphan document prefixes in object storage. IDs: %s",
            len(orphan_ids),
            preview,
        )
    return orphan_ids

