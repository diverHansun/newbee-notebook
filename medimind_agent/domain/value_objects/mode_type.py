"""
MediMind Agent - Mode Type Value Object
"""

from enum import Enum


class ModeType(str, Enum):
    """Chat interaction modes."""
    CHAT = "chat"       # General conversation
    ASK = "ask"         # Document-based Q&A
    EXPLAIN = "explain"  # Explain selected text
    CONCLUDE = "conclude"  # Summarize content


class MessageRole(str, Enum):
    """Message roles in conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


