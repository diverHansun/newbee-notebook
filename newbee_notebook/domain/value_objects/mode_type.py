"""
Newbee Notebook - Mode Type Value Object
"""

from enum import Enum


class ModeType(str, Enum):
    """Chat interaction modes."""
    AGENT = "agent"     # New runtime canonical mode
    CHAT = "chat"       # Compatibility alias for agent
    ASK = "ask"         # Document-based Q&A
    EXPLAIN = "explain"  # Explain selected text
    CONCLUDE = "conclude"  # Summarize content


class MessageRole(str, Enum):
    """Message roles in conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


def normalize_runtime_mode(mode: str | ModeType) -> ModeType:
    normalized = mode if isinstance(mode, ModeType) else ModeType(str(mode).strip().lower())
    if normalized is ModeType.CHAT:
        return ModeType.AGENT
    return normalized


