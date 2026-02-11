"""Generation module for building LlamaIndex query and chat engines.

This module provides utilities to build:
- Query engines for single-turn Q&A
- Chat engines for multi-turn conversations
"""

from newbee_notebook.core.rag.generation.query_engine import (
    build_query_engine,
    build_simple_query_engine,
)
from newbee_notebook.core.rag.generation.chat_engine import (
    build_chat_engine,
    build_simple_chat_engine,
)

__all__ = [
    # Query engines
    "build_query_engine",
    "build_simple_query_engine",
    # Chat engines
    "build_chat_engine",
    "build_simple_chat_engine",
]




