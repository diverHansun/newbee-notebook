"""Detect orphan document directories not referenced in database records."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable, List

from newbee_notebook.domain.repositories.document_repository import DocumentRepository

logger = logging.getLogger(__name__)

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _iter_document_dirs(documents_dir: Path) -> Iterable[Path]:
    if not documents_dir.exists() or not documents_dir.is_dir():
        return []
    return [p for p in documents_dir.iterdir() if p.is_dir() and UUID_PATTERN.match(p.name)]


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
) -> List[str]:
    """Return orphan document IDs that exist on disk but not in database."""
    root = Path(documents_dir)
    fs_dirs = list(_iter_document_dirs(root))
    if not fs_dirs:
        return []

    fs_ids = [d.name for d in fs_dirs]
    db_docs = await document_repo.get_batch(fs_ids)
    db_ids = {doc.document_id for doc in db_docs}

    orphan_ids = [doc_id for doc_id in fs_ids if doc_id not in db_ids]
    if not orphan_ids:
        return []

    total_size = sum(_dir_size_bytes(root / oid) for oid in orphan_ids)
    size_mb = total_size / (1024 * 1024)
    preview = ", ".join(orphan_ids[:5]) + ("..." if len(orphan_ids) > 5 else "")
    logger.warning(
        "Detected %d orphan document directories (%.1f MB). IDs: %s",
        len(orphan_ids),
        size_mb,
        preview,
    )
    return orphan_ids

