"""
MediMind Agent - Database Connection Module

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
    database = os.getenv("POSTGRES_DB", "medimind")
    
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
    
    async def connect(self) -> None:
        """Initialize the database connection."""
        self._engine = create_async_engine(
            self._url,
            echo=False,  # Set to True for SQL debugging
            poolclass=NullPool,  # Disable connection pooling for serverless
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    
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
        await _database.connect()
    return _database


async def close_database() -> None:
    """Close the global database instance."""
    global _database
    if _database is not None:
        await _database.disconnect()
        _database = None


