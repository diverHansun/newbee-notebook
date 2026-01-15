"""Modes module for different interaction patterns.

Each mode implements a specific interaction pattern:
- ChatMode: Agent-based with tools (no forced RAG)
- AskMode: Agent-based with RAG and hybrid retrieval
- ConcludeMode: Engine-based with RAG for summarization
- ExplainMode: Engine-based with RAG for explanation
"""

from src.engine.modes.base import BaseMode, ModeConfig
from src.engine.modes.chat_mode import ChatMode
from src.engine.modes.ask_mode import AskMode
from src.engine.modes.conclude_mode import ConcludeMode
from src.engine.modes.explain_mode import ExplainMode

__all__ = [
    "BaseMode",
    "ModeConfig",
    "ChatMode",
    "AskMode",
    "ConcludeMode",
    "ExplainMode",
]
