"""Engine module for Newbee Notebook interaction modes.

This module provides different conversation modes:
- ChatMode: Free-form conversation with web search and knowledge base tools
- AskMode: Deep Q&A with RAG and hybrid retrieval
- ConcludeMode: Document summarization and conclusion generation
- ExplainMode: Concept explanation and knowledge clarification

It also provides:
- ModeSelector: Factory for creating and managing modes
- IndexBuilder: Utilities for building pgvector and ES indexes
"""

from newbee_notebook.core.engine.modes.base import BaseMode, ModeConfig, ModeType
from newbee_notebook.core.engine.modes.chat_mode import ChatMode
from newbee_notebook.core.engine.modes.ask_mode import AskMode
from newbee_notebook.core.engine.modes.conclude_mode import ConcludeMode
from newbee_notebook.core.engine.modes.explain_mode import ExplainMode
from newbee_notebook.core.engine.selector import (
    ModeSelector,
    parse_mode_from_input,
    get_mode_help,
)
from newbee_notebook.core.engine.index_builder import (
    IndexBuilder,
    load_pgvector_index,
    load_es_index,
    load_pgvector_index_sync,
    load_es_index_sync,
)
from newbee_notebook.core.engine.mode_config import (
    LoopPolicy,
    ModeConfig as RuntimeModeConfig,
    ModeConfigFactory,
    SourcePolicy,
    ToolPolicy,
)
from newbee_notebook.core.engine.stream_events import (
    ContentEvent,
    DoneEvent,
    ErrorEvent,
    PhaseEvent,
    SourceEvent,
    StartEvent,
    ToolCallEvent,
    ToolResultEvent,
    WarningEvent,
)
from newbee_notebook.core.engine.session import SessionManager

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
    # Runtime config/events
    "LoopPolicy",
    "RuntimeModeConfig",
    "ModeConfigFactory",
    "SourcePolicy",
    "ToolPolicy",
    "ContentEvent",
    "DoneEvent",
    "ErrorEvent",
    "PhaseEvent",
    "SourceEvent",
    "StartEvent",
    "ToolCallEvent",
    "ToolResultEvent",
    "WarningEvent",
    # Session management
    "SessionManager",
]


