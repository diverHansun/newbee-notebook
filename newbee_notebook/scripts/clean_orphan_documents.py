"""Interactive cleaner for orphan document directories."""

from __future__ import annotations

import argparse
import asyncio
import shutil
from pathlib import Path

from newbee_notebook.infrastructure.persistence.database import get_database, close_database
from newbee_notebook.infrastructure.persistence.repositories.document_repo_impl import (
    DocumentRepositoryImpl,
)
from newbee_notebook.scripts.detect_orphans import detect_orphan_documents


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
    db = await get_database()

    async with db.session() as session:
        repo = DocumentRepositoryImpl(session)
        orphan_ids = await detect_orphan_documents(str(root), repo)

    if not orphan_ids:
        print("No orphan document directories found.")
        return 0

    print(f"Found {len(orphan_ids)} orphan document directories:")
    total_mb = 0.0
    for oid in orphan_ids:
        path = root / oid
        size_mb = _dir_size_mb(path)
        total_mb += size_mb
        print(f"  - {oid} ({size_mb:.1f} MB)")
    print(f"Total: {total_mb:.1f} MB")

    confirmed = assume_yes
    if not assume_yes:
        answer = input("Delete all listed directories? [y/N] ").strip().lower()
        confirmed = answer == "y"
    if not confirmed:
        print("Canceled.")
        return 0

    deleted = 0
    for oid in orphan_ids:
        target = root / oid
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
            print(f"Deleted: {target}")
            deleted += 1
    return deleted


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean orphan document directories.")
    parser.add_argument(
        "--documents-dir",
        default="data/documents",
        help="Root documents directory (default: data/documents).",
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
        print(f"Cleanup complete. Deleted {deleted} directory(ies).")
        return 0
    finally:
        await close_database()


def main() -> None:
    raise SystemExit(asyncio.run(_main_async()))


if __name__ == "__main__":
    main()

