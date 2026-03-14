"""Elasticsearch keyword retrieval helpers for the unified knowledge base tool."""

from __future__ import annotations

import json
import os
from typing import Optional

from elasticsearch import Elasticsearch


def _get_doc_id(metadata: dict) -> Optional[str]:
    for key in ("source_document_id", "document_id", "doc_id", "ref_doc_id"):
        value = metadata.get(key)
        if value:
            return str(value)
    return None


def _coerce_metadata(metadata: object) -> dict:
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    if not isinstance(metadata, dict):
        return {}
    return metadata


def _extract_hit_document_id(source: dict) -> Optional[str]:
    metadata = _coerce_metadata(source.get("metadata") or {})

    doc_id = _get_doc_id(metadata)
    if doc_id:
        return doc_id

    node_content = metadata.get("_node_content")
    if isinstance(node_content, str):
        try:
            node_content = json.loads(node_content)
        except json.JSONDecodeError:
            node_content = None
    if isinstance(node_content, dict):
        inner_meta = node_content.get("metadata") or {}
        if isinstance(inner_meta, dict):
            return _get_doc_id(inner_meta)
    return None


def es_search_with_raw(
    query: str,
    index_name: str = "newbee_notebook_docs",
    max_results: int = 5,
    es_url: Optional[str] = None,
    allowed_doc_ids: Optional[list[str]] = None,
) -> tuple[list[dict], str]:
    """Run BM25 keyword search and return raw + formatted results."""
    es_url = es_url or os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    allowed_set = set(allowed_doc_ids) if allowed_doc_ids is not None else None
    if allowed_set is not None and not allowed_set:
        return [], "No notebook-scoped documents are available for knowledge base search."

    es = Elasticsearch([es_url])

    if not es.indices.exists(index=index_name):
        return [], f"Index '{index_name}' does not exist. Please index documents first."

    bool_query = {
        "must": [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["content", "text", "title^2"],
                    "type": "best_fields",
                }
            }
        ]
    }
    if allowed_set is not None:
        ids = list(allowed_set)
        bool_query["filter"] = [
            {
                "bool": {
                    "should": [
                        {"terms": {"metadata.source_document_id.keyword": ids}},
                        {"terms": {"metadata.source_document_id": ids}},
                        {"terms": {"metadata.document_id.keyword": ids}},
                        {"terms": {"metadata.doc_id.keyword": ids}},
                        {"terms": {"metadata.ref_doc_id.keyword": ids}},
                        {"terms": {"metadata.document_id": ids}},
                        {"terms": {"metadata.doc_id": ids}},
                        {"terms": {"metadata.ref_doc_id": ids}},
                    ],
                    "minimum_should_match": 1,
                }
            }
        ]

    response = es.search(
        index=index_name,
        body={
            "query": {"bool": bool_query},
            "size": max_results,
            "_source": ["content", "text", "metadata"],
        },
    )

    hits = response.get("hits", {}).get("hits", [])
    if not hits:
        if allowed_set is None:
            return [], "No documents found matching your query in the knowledge base."
        return [], "No notebook-scoped documents found matching your query in the knowledge base."

    raw_results: list[dict] = []
    formatted_results: list[str] = []
    result_index = 0

    for hit in hits:
        source = hit.get("_source", {}) or {}
        doc_id = _extract_hit_document_id(source)
        if allowed_set is not None and doc_id not in allowed_set:
            continue

        result_index += 1
        metadata = _coerce_metadata(source.get("metadata") or {})
        title = metadata.get("title") or metadata.get("file_name") or f"Document {result_index}"
        content = source.get("content") or source.get("text") or "No content available"
        if len(content) > 500:
            content = content[:500] + "..."
        score = float(hit.get("_score", 0.0) or 0.0)

        raw_results.append(
            {
                "document_id": doc_id or "",
                "title": str(title),
                "score": score,
                "text": content,
                "chunk_id": "",
            }
        )
        formatted_results.append(
            f"{result_index}. [{title}] (score: {score:.2f})\n   {content}\n"
        )

    if not formatted_results:
        return [], "No notebook-scoped documents found matching your query in the knowledge base."
    return raw_results, "\n".join(formatted_results)


def es_search(
    query: str,
    index_name: str = "newbee_notebook_docs",
    max_results: int = 5,
    es_url: Optional[str] = None,
    allowed_doc_ids: Optional[list[str]] = None,
) -> str:
    _, formatted = es_search_with_raw(
        query=query,
        index_name=index_name,
        max_results=max_results,
        es_url=es_url,
        allowed_doc_ids=allowed_doc_ids,
    )
    return formatted


__all__ = ["es_search_with_raw", "es_search"]
