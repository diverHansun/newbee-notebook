"""Metadata filter utilities for hybrid retrieval compatibility.

Use a stable metadata key (`source_document_id`) for document scope pre-filtering.
This key is preserved across vector-store serialization and avoids the LlamaIndex
top-level ref_doc_id/document_id overwrite behavior.
"""

from typing import List, Optional, Tuple

from llama_index.core.vector_stores import FilterOperator, MetadataFilter, MetadataFilters


def build_document_filters(
    doc_ids: Optional[List[str]],
    key: str = "source_document_id",
) -> Tuple[Optional[MetadataFilters], Optional[MetadataFilters], Optional[List[str]]]:
    """Build per-backend filters and allowed IDs for hybrid retrieval.

    Returns a tuple: (pg_filters, es_filters, allowed_doc_ids)

    - pg_filters: pre-filter on stable source_document_id where possible
    - es_filters: only enabled for single-document scope because the current
      Elasticsearch vector-store adapter supports exact-match filters only
    - allowed_doc_ids: kept for post-filtering/fallback behavior
    """

    if doc_ids is None:
        return None, None, None

    scoped_ids = list(doc_ids)
    if not scoped_ids:
        return None, None, []

    if len(scoped_ids) == 1:
        eq_filter = MetadataFilters(
            filters=[
                MetadataFilter(
                    key=key,
                    value=scoped_ids[0],
                    operator=FilterOperator.EQ,
                )
            ]
        )
        return eq_filter, eq_filter, scoped_ids

    pg_filter = MetadataFilters(
        filters=[
            MetadataFilter(
                key=key,
                value=scoped_ids,
                operator=FilterOperator.IN,
            )
        ]
    )
    return pg_filter, None, scoped_ids


__all__ = ["build_document_filters"]
