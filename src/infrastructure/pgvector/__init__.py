"""PostgreSQL + pgvector integration module."""

from src.infrastructure.pgvector.store import PGVectorStore
from src.infrastructure.pgvector.config import PGVectorConfig

__all__ = ["PGVectorStore", "PGVectorConfig"]
