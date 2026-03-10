"""Interactive cleaner for orphan document storage entries."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from newbee_notebook.infrastructure.persistence.database import get_database, close_database
from newbee_notebook.infrastructure.persistence.repositories.document_repo_impl import (
    DocumentRepositoryImpl,
)
from newbee_notebook.scripts.detect_orphans import detect_orphan_documents
from newbee_notebook.infrastructure.storage import get_storage_backend
from newbee_notebook.infrastructure.storage.local_storage_backend import LocalStorageBackend


def _dir_size_mb(path: Path) -> float:
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total / (1024 * 1024)


async def run_cleanup(documents_dir: str, assume_yes: bool = False) -> int:
    root = Path(documents_dir)
    storage = get_storage_backend()
    db = await get_database()

    async with db.session() as session:
        repo = DocumentRepositoryImpl(session)
        orphan_ids = await detect_orphan_documents(
            str(root),
            repo,
            storage_backend=storage,
        )

    if not orphan_ids:
        print("No orphan document storage entries found.")
        return 0

    if isinstance(storage, LocalStorageBackend):
        print(f"Found {len(orphan_ids)} orphan document directories:")
        total_mb = 0.0
        for oid in orphan_ids:
            path = root / oid
            size_mb = _dir_size_mb(path)
            total_mb += size_mb
            print(f"  - {oid} ({size_mb:.1f} MB)")
        print(f"Total: {total_mb:.1f} MB")
    else:
        print(f"Found {len(orphan_ids)} orphan document prefixes in storage backend:")
        for oid in orphan_ids:
            objects = await storage.list_objects(f"{oid}/")
            print(f"  - {oid} ({len(objects)} object(s))")

    confirmed = assume_yes
    if not assume_yes:
        answer = input("Delete all listed entries? [y/N] ").strip().lower()
        confirmed = answer == "y"
    if not confirmed:
        print("Canceled.")
        return 0

    deleted = 0
    for oid in orphan_ids:
        deleted_count = await storage.delete_prefix(f"{oid}/")
        if deleted_count > 0:
            print(f"Deleted: {oid}/ ({deleted_count} object(s))")
            deleted += 1
    return deleted


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean orphan document entries from active storage.")
    parser.add_argument(
        "--documents-dir",
        default="data/documents",
        help=(
            "Local documents root for LocalStorageBackend mode "
            "(default: data/documents). Ignored when STORAGE_BACKEND=minio."
        ),
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Delete without interactive confirmation.",
    )
    return parser.parse_args()


async def _main_async() -> int:
    args = _parse_args()
    try:
        deleted = await run_cleanup(args.documents_dir, assume_yes=args.yes)
        storage = get_storage_backend()
        deleted_label = "directory(ies)" if isinstance(storage, LocalStorageBackend) else "storage prefix(es)"
        print(f"Cleanup complete. Deleted {deleted} {deleted_label}.")
        return 0
    finally:
        await close_database()


def main() -> None:
    raise SystemExit(asyncio.run(_main_async()))


if __name__ == "__main__":
    main()

