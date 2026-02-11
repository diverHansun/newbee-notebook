"""Utilities for mode source extraction.

Re-exports from core.common.node_utils for backwards compatibility.
New code should import directly from newbee_notebook.core.common.node_utils.
"""

from newbee_notebook.core.common.node_utils import (
    extract_document_id,
    _get_doc_id,
)

__all__ = ["extract_document_id", "_get_doc_id"]
