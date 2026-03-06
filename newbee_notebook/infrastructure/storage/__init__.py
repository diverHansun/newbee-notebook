"""Storage backends.

Factory function ``get_storage_backend()`` returns the active backend
selected by the ``STORAGE_BACKEND`` environment variable (default: "local").
"""

import os
from functools import lru_cache

from .base import StorageBackend
from .local_storage_backend import LocalStorageBackend


@lru_cache(maxsize=1)
def get_storage_backend() -> StorageBackend:
    """Create and cache the storage backend singleton.

    Environment variables:
        STORAGE_BACKEND: ``"local"`` (default) or ``"minio"``.

    When ``STORAGE_BACKEND=minio``, the following extra env vars are required:
        MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, etc.
    """
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
    if backend_type != "local":
        raise ValueError(
            f"Unsupported STORAGE_BACKEND={backend_type!r}; expected 'local' or 'minio'"
        )

    documents_dir = os.getenv("DOCUMENTS_DIR", "data/documents")
    return LocalStorageBackend(base_dir=documents_dir)


def reset_storage_backend() -> None:
    """Clear the cached backend (for testing)."""
    get_storage_backend.cache_clear()


__all__ = [
    "StorageBackend",
    "LocalStorageBackend",
    "get_storage_backend",
    "reset_storage_backend",
]
