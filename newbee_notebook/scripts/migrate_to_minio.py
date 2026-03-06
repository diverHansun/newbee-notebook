"""Migrate local document files into MinIO object storage."""

from __future__ import annotations

import argparse
import asyncio
import mimetypes
import os
import re
from dataclasses import dataclass
from pathlib import Path

from newbee_notebook.infrastructure.storage.minio_storage_backend import MinIOStorageBackend

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@dataclass
class MigrationStats:
    total_files: int = 0
    migrated_files: int = 0
    total_bytes: int = 0
    migrated_bytes: int = 0
    failed_files: int = 0


def _build_minio_backend_from_env() -> MinIOStorageBackend:
    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
    bucket = os.getenv("MINIO_BUCKET", "documents")
    secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
    public_endpoint = os.getenv("MINIO_PUBLIC_ENDPOINT")

    return MinIOStorageBackend(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        bucket_name=bucket,
        secure=secure,
        public_endpoint=public_endpoint,
    )


def _collect_local_files(documents_dir: Path) -> list[Path]:
    files: list[Path] = []
    for doc_dir in sorted(documents_dir.iterdir()):
        if not doc_dir.is_dir() or not UUID_PATTERN.match(doc_dir.name):
            continue
        files.extend([p for p in doc_dir.rglob("*") if p.is_file()])
    return sorted(files)


def _to_object_key(file_path: Path, documents_dir: Path) -> str:
    return file_path.relative_to(documents_dir).as_posix()


async def migrate_documents_to_minio(
    documents_dir: Path,
    backend: MinIOStorageBackend,
    *,
    dry_run: bool = False,
) -> MigrationStats:
    files = _collect_local_files(documents_dir)
    stats = MigrationStats(total_files=len(files))

    if not files:
        return stats

    for idx, file_path in enumerate(files, start=1):
        object_key = _to_object_key(file_path, documents_dir)
        size = file_path.stat().st_size
        stats.total_bytes += size

        if dry_run:
            stats.migrated_files += 1
            stats.migrated_bytes += size
            if idx <= 5:
                print(f"[DRY-RUN] {object_key}")
            continue

        content_type, _ = mimetypes.guess_type(str(file_path))
        try:
            await backend.save_from_path(
                object_key=object_key,
                local_path=str(file_path),
                content_type=content_type or "application/octet-stream",
            )
            stats.migrated_files += 1
            stats.migrated_bytes += size
        except Exception as exc:  # noqa: BLE001
            stats.failed_files += 1
            print(f"[ERROR] {object_key}: {exc}")

        if idx % 500 == 0:
            print(f"Progress: {idx}/{len(files)}")

    return stats


async def verify_migration(
    documents_dir: Path,
    backend: MinIOStorageBackend,
) -> tuple[int, list[str]]:
    local_keys = {_to_object_key(path, documents_dir) for path in _collect_local_files(documents_dir)}
    remote_keys = set(await backend.list_objects(""))
    missing = sorted(local_keys - remote_keys)
    return len(local_keys), missing


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate local document files to MinIO.")
    parser.add_argument(
        "--documents-dir",
        default="data/documents",
        help="Local documents directory (default: data/documents)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration without uploading to MinIO",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify that every local file exists in MinIO after migration",
    )
    return parser.parse_args()


async def _main_async() -> int:
    args = _parse_args()
    documents_dir = Path(args.documents_dir)
    if not documents_dir.exists():
        print(f"Documents directory not found: {documents_dir}")
        return 1

    backend = _build_minio_backend_from_env()
    stats = await migrate_documents_to_minio(
        documents_dir=documents_dir,
        backend=backend,
        dry_run=args.dry_run,
    )

    print("Migration summary:")
    print(f"  total_files={stats.total_files}")
    print(f"  migrated_files={stats.migrated_files}")
    print(f"  failed_files={stats.failed_files}")
    print(f"  total_bytes={stats.total_bytes}")
    print(f"  migrated_bytes={stats.migrated_bytes}")

    if args.verify and not args.dry_run:
        total, missing = await verify_migration(documents_dir, backend)
        print("Verification summary:")
        print(f"  local_files={total}")
        print(f"  missing_in_minio={len(missing)}")
        if missing:
            print(f"  missing_sample={missing[0]}")
            return 2

    return 0 if stats.failed_files == 0 else 2


def main() -> None:
    raise SystemExit(asyncio.run(_main_async()))


if __name__ == "__main__":
    main()
