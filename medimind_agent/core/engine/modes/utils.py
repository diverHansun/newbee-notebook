"""Utilities for mode source extraction.

Re-exports from core.common.node_utils for backwards compatibility.
New code should import directly from medimind_agent.core.common.node_utils.
"""

from medimind_agent.core.common.node_utils import (
    extract_document_id,
    _get_doc_id,
)

__all__ = ["extract_document_id", "_get_doc_id"]
