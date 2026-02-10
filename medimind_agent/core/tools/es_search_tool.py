"""Elasticsearch search tool for Chat mode.

This module provides an Elasticsearch-based search tool that can be used
as a FunctionTool in the Chat mode FunctionAgent. It performs BM25 keyword
search against the document index.
"""

import json
import os
from typing import List, Optional, Set

from elasticsearch import Elasticsearch
from llama_index.core.tools import FunctionTool


def _get_doc_id(metadata: dict) -> Optional[str]:
    """Return first available document id from metadata."""
    for key in ("document_id", "doc_id", "ref_doc_id"):
        value = metadata.get(key)
        if value:
            return value
    return None


def _extract_hit_document_id(source: dict) -> Optional[str]:
    """Extract document_id from ES hit _source payload."""
    metadata = source.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}

    doc_id = _get_doc_id(metadata)
    if doc_id:
        return doc_id

    node_content = metadata.get("_node_content")
    if node_content:
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


def _es_search(
    query: str,
    index_name: str = "medimind_docs",
    max_results: int = 5,
    es_url: Optional[str] = None,
    allowed_doc_ids: Optional[List[str]] = None,
) -> str:
    """Search documents using Elasticsearch BM25.

    Args:
        query: Search query string
        index_name: Elasticsearch index name
        max_results: Maximum number of results to return
        es_url: Elasticsearch URL (defaults to ELASTICSEARCH_URL env var)
        allowed_doc_ids: Optional notebook-scoped document IDs

    Returns:
        Formatted search results as a string
    """
    es_url = es_url or os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    allowed_set: Optional[Set[str]]
    if allowed_doc_ids is None:
        allowed_set = None
    else:
        allowed_set = set(allowed_doc_ids)
        if not allowed_set:
            return "No notebook-scoped documents are available for knowledge base search."

    # Create Elasticsearch client
    es = Elasticsearch([es_url])

    # Check if index exists
    if not es.indices.exists(index=index_name):
        return f"Index '{index_name}' does not exist. Please index documents first."

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

    # Execute BM25 search
    response = es.search(
        index=index_name,
        body={
            "query": {"bool": bool_query},
            "size": max_results,
            "_source": ["content", "text", "metadata"],
        },
    )

    # Format results
    hits = response.get("hits", {}).get("hits", [])

    if not hits:
        if allowed_set is None:
            return "No documents found matching your query in the knowledge base."
        return "No notebook-scoped documents found matching your query in the knowledge base."

    results = []
    result_index = 0
    for hit in hits:
        score = hit.get("_score", 0)
        source = hit.get("_source", {})
        doc_id = _extract_hit_document_id(source)
        if allowed_set is not None and doc_id not in allowed_set:
            continue

        result_index += 1
        # Get content from various possible fields
        content = (
            source.get("content")
            or source.get("text")
            or "No content available"
        )

        # Truncate long content
        if len(content) > 500:
            content = content[:500] + "..."

        metadata = source.get("metadata", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        doc_title = metadata.get("title", metadata.get("file_name", f"Document {result_index}"))

        results.append(
            f"{result_index}. [{doc_title}] (score: {score:.2f})\n"
            f"   {content}\n"
        )

    if not results:
        return "No notebook-scoped documents found matching your query in the knowledge base."
    return "\n".join(results)


class ElasticsearchSearchTool:
    """Elasticsearch search tool wrapper.

    This class provides a clean interface for creating Elasticsearch search
    tools that can be used with LlamaIndex agents.

    Attributes:
        index_name: Name of the Elasticsearch index
        max_results: Maximum number of search results
        es_url: Elasticsearch URL
        _tool: Internal FunctionTool instance
    """

    def __init__(
        self,
        index_name: str = "medimind_docs",
        max_results: int = 5,
        es_url: Optional[str] = None,
        allowed_doc_ids: Optional[List[str]] = None,
    ):
        """Initialize ElasticsearchSearchTool.

        Args:
            index_name: Elasticsearch index name (default: medimind_docs)
            max_results: Maximum number of results (default: 5)
            es_url: Elasticsearch URL (default: from env)
            allowed_doc_ids: Optional notebook-scoped document IDs
        """
        self.index_name = index_name
        self.max_results = max_results
        self.es_url = es_url or os.getenv(
            "ELASTICSEARCH_URL", "http://localhost:9200"
        )
        self.allowed_doc_ids = allowed_doc_ids
        self._tool: Optional[FunctionTool] = None

    def get_tool(self) -> FunctionTool:
        """Get the FunctionTool instance for use with agents.

        Returns:
            FunctionTool instance configured for ES search
        """
        if self._tool is None:
            self._tool = FunctionTool.from_defaults(
                fn=self._search,
                name="knowledge_base_search",
                description=(
                    "Search notebook-scoped knowledge base documents. "
                    "Use this when the user asks about content from the indexed notebook files. "
                    "Input should be a search query string."
                ),
            )
        return self._tool

    def _search(self, query: str) -> str:
        """Internal search method.

        Args:
            query: Search query string

        Returns:
            Formatted search results
        """
        return _es_search(
            query=query,
            index_name=self.index_name,
            max_results=self.max_results,
            es_url=self.es_url,
            allowed_doc_ids=self.allowed_doc_ids,
        )


def build_es_search_tool(
    index_name: str = "medimind_docs",
    max_results: int = 5,
    es_url: Optional[str] = None,
    allowed_doc_ids: Optional[List[str]] = None,
) -> FunctionTool:
    """Build an Elasticsearch search FunctionTool.

    Convenience function for quickly creating an ES search tool.

    Args:
        index_name: Elasticsearch index name
        max_results: Maximum number of results
        es_url: Elasticsearch URL
        allowed_doc_ids: Optional notebook-scoped document IDs

    Returns:
        FunctionTool configured for ES BM25 search

    Example:
        >>> tool = build_es_search_tool(index_name="my_docs")
        >>> agent = FunctionAgent(tools=[tool], llm=llm)
    """
    return ElasticsearchSearchTool(
        index_name=index_name,
        max_results=max_results,
        es_url=es_url,
        allowed_doc_ids=allowed_doc_ids,
    ).get_tool()

