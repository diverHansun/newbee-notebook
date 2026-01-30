"""Utilities for LlamaIndex node metadata extraction.

This module is placed in core/common to avoid circular imports.
It should NOT import from core/engine/modes or core/rag/retrieval.
"""

from __future__ import annotations

import json
from typing import Any, Optional


def _get_doc_id(meta: dict) -> Optional[str]:
    """Return the first present document id key from metadata dict."""
    for key in ("document_id", "doc_id", "ref_doc_id"):
        value = meta.get(key)
        if value:
            return value
    return None


def extract_document_id(node: Any) -> Optional[str]:
    """Extract the correct document_id from a LlamaIndex node or NodeWithScore.

    LlamaIndex may overwrite top-level metadata.document_id/ref_doc_id during
    insert_nodes() with internal parent node IDs. The original document id is
    preserved in `_node_content.metadata`. This helper prefers that location
    and falls back to the top-level metadata.
    """
    node_obj = getattr(node, "node", node)
    metadata = getattr(node_obj, "metadata", {}) or {}

    # 1) Prefer _node_content.metadata.*
    node_content = metadata.get("_node_content")
    if node_content:
        if isinstance(node_content, str):
            try:
                node_content = json.loads(node_content)
            except json.JSONDecodeError:
                node_content = None
        if isinstance(node_content, dict):
            inner_meta = node_content.get("metadata") or {}
            doc_id = _get_doc_id(inner_meta)
            if doc_id:
                return doc_id

    # 2) Fallback to top-level metadata (may be overwritten)
    return _get_doc_id(metadata)
