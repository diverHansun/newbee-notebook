"""
Newbee Notebook - Database Connection Module

Provides async database connection using SQLAlchemy.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool
from sqlalchemy import text

_schema_checked = False


def get_runtime_schema_statements() -> list[str]:
    return [
        """
        ALTER TABLE IF EXISTS documents
        ADD COLUMN IF NOT EXISTS processing_stage VARCHAR(64)
        """,
        """
        ALTER TABLE IF EXISTS documents
        ADD COLUMN IF NOT EXISTS stage_updated_at TIMESTAMP
        """,
        """
        ALTER TABLE IF EXISTS documents
        ADD COLUMN IF NOT EXISTS processing_meta TEXT
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_documents_stage_updated_at
        ON documents(stage_updated_at)
        """,
        """
        ALTER TABLE IF EXISTS sessions
        ADD COLUMN IF NOT EXISTS include_ec_context BOOLEAN NOT NULL DEFAULT FALSE
        """,
        """
        UPDATE messages SET mode = 'agent' WHERE mode = 'chat'
        """,
        """
        ALTER TABLE IF EXISTS messages
        DROP CONSTRAINT IF EXISTS messages_mode_check
        """,
        """
        ALTER TABLE IF EXISTS messages
        ADD CONSTRAINT messages_mode_check
        CHECK (mode IN ('agent','ask','conclude','explain'))
        """,
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            key         VARCHAR(128) PRIMARY KEY,
            value       TEXT NOT NULL,
            updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS marks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            anchor_text TEXT NOT NULL,
            char_offset INTEGER NOT NULL CHECK (char_offset >= 0),
            context_text TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_marks_document_id
        ON marks(document_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_marks_created_at
        ON marks(created_at)
        """,
        """
        CREATE TABLE IF NOT EXISTS notes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
            title TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_notes_notebook_id
        ON notes(notebook_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_notes_updated_at
        ON notes(updated_at)
        """,
        """
        CREATE TABLE IF NOT EXISTS note_document_tags (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            note_id UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(note_id, document_id)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_note_document_tags_note_id
        ON note_document_tags(note_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_note_document_tags_document_id
        ON note_document_tags(document_id)
        """,
        """
        CREATE TABLE IF NOT EXISTS note_mark_refs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            note_id UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            mark_id UUID NOT NULL REFERENCES marks(id) ON DELETE CASCADE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(note_id, mark_id)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_note_mark_refs_note_id
        ON note_mark_refs(note_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_note_mark_refs_mark_id
        ON note_mark_refs(mark_id)
        """,
        """
        CREATE TABLE IF NOT EXISTS diagrams (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            diagram_type TEXT NOT NULL,
            format TEXT NOT NULL CHECK (format IN ('reactflow_json', 'mermaid')),
            content_path TEXT NOT NULL,
            document_ids UUID[] NOT NULL DEFAULT '{}',
            node_positions JSONB,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_diagrams_notebook_id
        ON diagrams(notebook_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_diagrams_document_ids
        ON diagrams USING GIN(document_ids)
        """,
    ]


def get_database_url() -> str:
    """
    Get the database URL from environment variables.
    
    Returns:
        PostgreSQL async connection URL.
    """
    # Read from environment or use defaults
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    database = os.getenv("POSTGRES_DB", "newbee_notebook")
    
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


class Database:
    """
    Async database connection manager.
    
    Usage:
        db = Database()
        await db.connect()
        
        async with db.session() as session:
            # Use session
            pass
        
        await db.disconnect()
    """
    
    def __init__(self, url: str = None):
        self._url = url or get_database_url()
        self._engine: AsyncEngine = None
        self._session_factory: async_sessionmaker = None

    @property
    def is_connected(self) -> bool:
        return self._engine is not None and self._session_factory is not None
    
    async def connect(self) -> None:
        """Initialize the database connection."""
        global _schema_checked
        if self.is_connected:
            return

        engine = create_async_engine(
            self._url,
            echo=False,  # Set to True for SQL debugging
            poolclass=NullPool,  # Disable connection pooling for serverless
        )
        self._engine = engine
        try:
            if not _schema_checked:
                await self._ensure_runtime_schema()
                _schema_checked = True
            self._session_factory = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        except Exception:
            self._session_factory = None
            self._engine = None
            await engine.dispose()
            raise

    async def _ensure_runtime_schema(self) -> None:
        """Best-effort schema backfill for additive columns used by new releases."""
        if not self._engine:
            return
        async with self._engine.begin() as conn:
            for statement in get_runtime_schema_statements():
                await conn.execute(text(statement))
    
    async def disconnect(self) -> None:
        """Close the database connection."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session context.
        
        Usage:
            async with db.session() as session:
                # Use session
                await session.execute(...)
        """
        if not self._session_factory:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session with explicit transaction control.
        
        Same as session(), but makes transaction semantics explicit.
        """
        async with self.session() as session:
            yield session


# Global database instance
_database: Database = None


async def get_database() -> Database:
    """Get or create the global database instance."""
    global _database
    if _database is None:
        _database = Database()
    if not _database.is_connected:
        await _database.connect()
    return _database


async def close_database() -> None:
    """Close the global database instance."""
    global _database
    if _database is not None:
        await _database.disconnect()
        _database = None


