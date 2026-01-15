"""Data models for chat sessions and messages.

This module defines the domain models following Domain-Driven Design (DDD)
principles and Single Responsibility Principle (SRP).
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class ModeType(str, Enum):
    """Chat mode types."""
    
    CHAT = "chat"
    ASK = "ask"
    CONCLUDE = "conclude"
    EXPLAIN = "explain"


class MessageRole(str, Enum):
    """Message roles in a conversation."""
    
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """Represents a single message in a chat session.
    
    Attributes:
        id: Message ID (auto-generated)
        session_id: ID of the parent session
        mode: Mode type when message was created
        role: Role of the message sender
        content: Message content
        created_at: Timestamp when message was created
    """
    
    id: Optional[int] = None
    session_id: UUID
    mode: ModeType
    role: MessageRole
    content: str
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        """Pydantic config."""
        use_enum_values = True


class ChatSession(BaseModel):
    """Represents a chat session.
    
    A session can contain messages from multiple modes, allowing mode
    switching within the same conversation context.
    
    Attributes:
        session_id: Unique session identifier
        created_at: Timestamp when session was created
        updated_at: Timestamp when session was last updated
    """
    
    session_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        """Pydantic config."""
        from_attributes = True
