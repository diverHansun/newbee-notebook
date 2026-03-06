"""Delete one document's files from the active storage backend."""

from __future__ import annotations

import argparse
import asyncio
import re

from newbee_notebook.infrastructure.storage import get_storage_backend

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delete one document from active storage backend.")
    parser.add_argument("--id", required=True, help="Document UUID")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Delete without interactive confirmation",
    )
    return parser.parse_args()


async def _main_async() -> int:
    args = _parse_args()
    doc_id = args.id.strip()
    if not UUID_PATTERN.match(doc_id):
        print("Invalid document id format. Expected UUID.")
        return 1

    backend = get_storage_backend()
    object_keys = await backend.list_objects(f"{doc_id}/")
    if not object_keys:
        print(f"No files found for document: {doc_id}")
        return 0

    print(f"Found {len(object_keys)} object(s) under {doc_id}/")
    for key in object_keys[:10]:
        print(f"  - {key}")
    if len(object_keys) > 10:
        print(f"  ... ({len(object_keys) - 10} more)")

    confirmed = args.yes
    if not confirmed:
        answer = input("Delete all listed objects? [y/N] ").strip().lower()
        confirmed = answer == "y"

    if not confirmed:
        print("Canceled.")
        return 0

    deleted_count = await backend.delete_prefix(f"{doc_id}/")
    print(f"Deleted {deleted_count} object(s) for {doc_id}/")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main_async()))


if __name__ == "__main__":
    main()
