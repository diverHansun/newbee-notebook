"""
Newbee Notebook - Session Entity

A Session represents a conversation within a Notebook.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from newbee_notebook.domain.entities.base import Entity, generate_uuid


# Threshold for message compression (10 rounds = 20 messages)
COMPRESSION_THRESHOLD_ROUNDS = 10


@dataclass
class Session(Entity):
    """
    Session entity - a conversation within a Notebook.
    
    Each Notebook can have up to 20 Sessions.
    When messages exceed the threshold, old messages are compressed
    into a summary stored in context_summary.
    
    Attributes:
        session_id: Unique identifier
        notebook_id: Parent notebook ID
        title: Optional session title
        message_count: Number of messages in this session
        context_summary: Compressed history summary for context management
    """
    session_id: str = field(default_factory=generate_uuid)
    notebook_id: str = ""
    title: Optional[str] = None
    message_count: int = 0
    context_summary: Optional[str] = None
    
    @property
    def round_count(self) -> int:
        """Get the number of conversation rounds (1 round = 2 messages)."""
        return self.message_count // 2
    
    @property
    def needs_compression(self) -> bool:
        """Check if conversation history needs compression."""
        return self.round_count > COMPRESSION_THRESHOLD_ROUNDS
    
    def increment_message_count(self, delta: int = 1) -> None:
        """Increment the message count."""
        self.message_count += delta
        self.touch()
    
    def update_context_summary(self, summary: str) -> None:
        """Update the context summary."""
        self.context_summary = summary
        self.touch()


