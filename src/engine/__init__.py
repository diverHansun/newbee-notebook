"""Engine module for MediMind Agent interaction modes.

This module provides different conversation modes:
- ChatMode: Free-form conversation with web search and knowledge base tools
- AskMode: Deep Q&A with RAG and hybrid retrieval
- ConcludeMode: Document summarization and conclusion generation
- ExplainMode: Concept explanation and knowledge clarification

It also provides:
- ModeSelector: Factory for creating and managing modes
- IndexBuilder: Utilities for building pgvector and ES indexes
"""

from src.engine.modes.base import BaseMode, ModeConfig, ModeType
from src.engine.modes.chat_mode import ChatMode
from src.engine.modes.ask_mode import AskMode
from src.engine.modes.conclude_mode import ConcludeMode
from src.engine.modes.explain_mode import ExplainMode
from src.engine.selector import (
    ModeSelector,
    parse_mode_from_input,
    get_mode_help,
)
from src.engine.index_builder import (
    IndexBuilder,
    load_pgvector_index,
    load_es_index,
    load_pgvector_index_sync,
    load_es_index_sync,
)
from src.engine.session import SessionManager

__all__ = [
    # Modes
    "BaseMode",
    "ModeConfig",
    "ModeType",
    "ChatMode",
    "AskMode",
    "ConcludeMode",
    "ExplainMode",
    # Selector
    "ModeSelector",
    "parse_mode_from_input",
    "get_mode_help",
    # Index utilities
    "IndexBuilder",
    "load_pgvector_index",
    "load_es_index",
    "load_pgvector_index_sync",
    "load_es_index_sync",
    # Session management
    "SessionManager",
]
