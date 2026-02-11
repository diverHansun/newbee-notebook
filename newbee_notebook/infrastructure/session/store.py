"""Chat session storage implementation using PostgreSQL.

This module provides persistent storage for chat sessions and messages,
following the Repository Pattern and Single Responsibility Principle (SRP).
"""

import asyncpg
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from newbee_notebook.infrastructure.session.models import (
    ChatSession,
    ChatMessage,
    ModeType,
    MessageRole,
)
from newbee_notebook.infrastructure.pgvector.config import PGVectorConfig


class ChatSessionStore:
    """PostgreSQL-based storage for chat sessions and messages.
    
    This class manages the persistence of chat sessions and their messages,
    providing a clean interface for CRUD operations.
    
    Attributes:
        config: PGVectorConfig instance with connection parameters
        _pool: Connection pool to PostgreSQL
    """
    
    def __init__(self, config: PGVectorConfig):
        """Initialize ChatSessionStore.
        
        Args:
            config: PGVectorConfig instance with connection parameters
        """
        self.config = config
        self._pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self) -> None:
        """Initialize the session store and create tables if needed."""
        # Create connection pool
        self._pool = await asyncpg.create_pool(
            host=self.config.host,
            port=self.config.port,
            database=self.config.database,
            user=self.config.user,
            password=self.config.password,
            min_size=1,
            max_size=10,
        )
        
        # Create tables
        await self._create_tables()
    
    async def _create_tables(self) -> None:
        """Create chat_sessions and chat_messages tables if they don't exist."""
        async with self._pool.acquire() as conn:
            # Create sessions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id UUID PRIMARY KEY,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            
            # Create messages table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id SERIAL PRIMARY KEY,
                    session_id UUID NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
                    mode VARCHAR(20) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            
            # Create index on session_id for faster queries
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id 
                ON chat_messages(session_id)
            """)
    
    async def create_session(self) -> ChatSession:
        """Create a new chat session.
        
        Returns:
            ChatSession instance with generated session_id
        """
        session = ChatSession()
        
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO chat_sessions (session_id, created_at, updated_at)
                VALUES ($1, $2, $3)
                """,
                session.session_id,
                session.created_at,
                session.updated_at,
            )
        
        return session
    
    async def get_session(self, session_id: UUID) -> Optional[ChatSession]:
        """Get a chat session by ID.
        
        Args:
            session_id: UUID of the session
            
        Returns:
            ChatSession instance if found, None otherwise
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT session_id, created_at, updated_at
                FROM chat_sessions
                WHERE session_id = $1
                """,
                session_id,
            )
            
            if row is None:
                return None
            
            return ChatSession(
                session_id=row["session_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
    
    async def add_message(self, message: ChatMessage) -> ChatMessage:
        """Add a message to a session.
        
        Args:
            message: ChatMessage instance to add
            
        Returns:
            ChatMessage instance with generated ID
            
        Raises:
            ValueError: If session doesn't exist
        """
        async with self._pool.acquire() as conn:
            # Check if session exists
            session_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM chat_sessions WHERE session_id = $1)",
                message.session_id,
            )
            
            if not session_exists:
                raise ValueError(f"Session {message.session_id} does not exist")
            
            # Insert message
            message_id = await conn.fetchval(
                """
                INSERT INTO chat_messages (session_id, mode, role, content, created_at)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                message.session_id,
                message.mode,
                message.role,
                message.content,
                message.created_at,
            )
            
            # Update session's updated_at
            await conn.execute(
                """
                UPDATE chat_sessions
                SET updated_at = $1
                WHERE session_id = $2
                """,
                datetime.now(),
                message.session_id,
            )
            
            message.id = message_id
            return message
    
    async def get_messages(
        self,
        session_id: UUID,
        mode: Optional[ModeType] = None,
        limit: Optional[int] = None,
        descending: bool = False,
    ) -> List[ChatMessage]:
        """Get messages for a session.
        
        Args:
            session_id: UUID of the session
            mode: Optional filter by mode type
            limit: Optional limit on number of messages
            
        Returns:
            List of ChatMessage instances, ordered by creation time
        """
        async with self._pool.acquire() as conn:
            order_dir = "DESC" if descending else "ASC"
            if mode is None:
                query = f"""
                    SELECT id, session_id, mode, role, content, created_at
                    FROM chat_messages
                    WHERE session_id = $1
                    ORDER BY created_at {order_dir}
                """
                params = [session_id]
            else:
                query = f"""
                    SELECT id, session_id, mode, role, content, created_at
                    FROM chat_messages
                    WHERE session_id = $1 AND mode = $2
                    ORDER BY created_at {order_dir}
                """
                params = [session_id, mode.value]
            
            if limit is not None:
                query += f" LIMIT ${len(params) + 1}"
                params.append(limit)
            
            rows = await conn.fetch(query, *params)
            
            messages = [
                ChatMessage(
                    id=row["id"],
                    session_id=row["session_id"],
                    mode=ModeType(row["mode"]),
                    role=MessageRole(row["role"]),
                    content=row["content"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]
            if descending:
                messages.reverse()  # return oldest->newest to callers
            return messages

    async def list_sessions(self, limit: int = 20) -> List[ChatSession]:
        """List recent sessions ordered by updated_at desc."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT session_id, created_at, updated_at
                FROM chat_sessions
                ORDER BY updated_at DESC
                LIMIT $1
                """,
                limit,
            )
            return [
                ChatSession(
                    session_id=row["session_id"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]
    
    async def delete_session(self, session_id: UUID) -> None:
        """Delete a session and all its messages.
        
        Args:
            session_id: UUID of the session to delete
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM chat_sessions WHERE session_id = $1",
                session_id,
            )
    
    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


