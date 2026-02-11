"""
Indexing utilities (stub for tests).

This lightweight module provides a minimal `build_index_if_not_exists`
to satisfy integration test imports without performing heavy IO.
"""

from pathlib import Path
from typing import Any, Optional


def build_index_if_not_exists(
    documents_dir: str | Path,
    embed_model: Any,
    persist_dir: str | Path,
    **kwargs,
) -> Optional[Any]:
    """
    Placeholder index builder.

    In the current scope we avoid heavy indexing; this function simply returns None.
    """
    return None

