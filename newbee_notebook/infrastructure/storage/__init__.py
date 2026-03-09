"""Storage backend factories for runtime and offline usage."""

import os
from functools import lru_cache

from .base import StorageBackend
from .local_storage_backend import LocalStorageBackend


def _build_storage_backend(*, allow_local: bool) -> StorageBackend:
    """Build a storage backend from env configuration."""
    backend_type = os.getenv("STORAGE_BACKEND", "local").lower()

    if backend_type == "minio":
        from .minio_storage_backend import MinIOStorageBackend

        return MinIOStorageBackend(
            endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin123"),
            bucket_name=os.getenv("MINIO_BUCKET", "documents"),
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
            public_endpoint=os.getenv("MINIO_PUBLIC_ENDPOINT"),
        )
    if backend_type == "local":
        if not allow_local:
            raise RuntimeError("Runtime storage backend requires MinIO (STORAGE_BACKEND=minio)")

        documents_dir = os.getenv("DOCUMENTS_DIR", "data/documents")
        return LocalStorageBackend(base_dir=documents_dir)

    if backend_type != "local":
        raise ValueError(
            f"Unsupported STORAGE_BACKEND={backend_type!r}; expected 'local' or 'minio'"
        )


@lru_cache(maxsize=1)
def get_storage_backend() -> StorageBackend:
    """Create and cache the offline/test storage backend singleton."""
    return _build_storage_backend(allow_local=True)


@lru_cache(maxsize=1)
def get_runtime_storage_backend() -> StorageBackend:
    """Create and cache the runtime storage backend singleton."""
    return _build_storage_backend(allow_local=False)


def reset_storage_backend() -> None:
    """Clear cached backends (for testing)."""
    get_storage_backend.cache_clear()
    get_runtime_storage_backend.cache_clear()


__all__ = [
    "StorageBackend",
    "LocalStorageBackend",
    "get_runtime_storage_backend",
    "get_storage_backend",
    "reset_storage_backend",
]
