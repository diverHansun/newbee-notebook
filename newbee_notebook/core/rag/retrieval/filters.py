"""Metadata filter utilities for hybrid retrieval compatibility.

Pre-filters are DISABLED because LlamaIndex overwrites ref_doc_id during
insert_nodes() with its internal parent node ID. We rely solely on post-filtering
with allowed_doc_ids, which uses deserialized _node_content.metadata that
preserves our original document IDs.
"""

from typing import List, Optional, Tuple

from llama_index.core.vector_stores import MetadataFilters


def build_document_filters(
    doc_ids: Optional[List[str]],
    key: str = "ref_doc_id",  # kept for API compatibility
) -> Tuple[Optional[MetadataFilters], Optional[MetadataFilters], Optional[List[str]]]:
    """Build per-backend filters and allowed IDs for hybrid retrieval.

    Returns a tuple: (pg_filters, es_filters, allowed_doc_ids)

    NOTE: Pre-filters are disabled because LlamaIndex overwrites metadata.ref_doc_id
    with internal node IDs during insert. Post-filtering uses deserialized
    _node_content.metadata which preserves our original document IDs.

    - pg_filters: None (disabled)
    - es_filters: None (disabled)
    - allowed_doc_ids: used for post-filtering after fusion
    """

    if doc_ids is None:
        return None, None, None

    # Disable pre-filters, rely on post-filter with allowed_doc_ids
    return None, None, list(doc_ids)


__all__ = ["build_document_filters"]
