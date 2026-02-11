"""PostgreSQL + pgvector integration module."""

from newbee_notebook.infrastructure.pgvector.store import PGVectorStore
from newbee_notebook.infrastructure.pgvector.config import PGVectorConfig

__all__ = ["PGVectorStore", "PGVectorConfig"]


