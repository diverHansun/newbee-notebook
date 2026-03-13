"""Infrastructure module for storage backends and external services."""

from newbee_notebook.infrastructure.pgvector.store import PGVectorStore

__all__ = [
    "PGVectorStore",
]


