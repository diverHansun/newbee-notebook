"""Unified knowledge-base retrieval tool for the batch-2 runtime."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from llama_index.core.schema import QueryBundle

from newbee_notebook.core.common.node_utils import extract_document_id
from newbee_notebook.core.rag.retrieval.filters import build_document_filters
from newbee_notebook.core.rag.retrieval import build_hybrid_retriever
from newbee_notebook.core.rag.retrieval.scoped_retriever import ScopedRetriever
from newbee_notebook.core.tools.contracts import (
    SourceItem,
    ToolCallResult,
    ToolDefinition,
    ToolQualityMeta,
)
from newbee_notebook.core.rag.retrieval.es_keyword import es_search_with_raw


SearchPayload = dict[str, Any]
SearchResult = dict[str, Any]
SearchExecutor = Callable[[SearchPayload], Awaitable[list[SearchResult]]]


def _dedupe_preserve_order(values: Sequence[str] | None) -> list[str] | None:
    if values is None:
        return None
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _resolve_scope(
    *,
    allowed_document_ids: Sequence[str] | None,
    filter_document_id: str | None,
) -> tuple[str, list[str] | None]:
    scoped_allowed = _dedupe_preserve_order(allowed_document_ids)
    scoped_filter = str(filter_document_id).strip() if filter_document_id else None
    if not scoped_filter:
        return "notebook", scoped_allowed
    if scoped_allowed is None:
        return "document", [scoped_filter]
    if scoped_filter not in scoped_allowed:
        return "document", []
    return "document", [scoped_filter]


def _quality_band(result_count: int, max_score: float | None) -> str:
    if result_count <= 0:
        return "empty"
    if result_count >= 2 and (max_score or 0.0) >= 0.75:
        return "high"
    if (max_score or 0.0) >= 0.35:
        return "medium"
    return "low"


def _build_quality_meta(
    *,
    scope_used: str,
    search_type: str,
    results: list[SearchResult],
) -> ToolQualityMeta:
    scores = [float(item.get("score", 0.0) or 0.0) for item in results]
    max_score = max(scores) if scores else None
    band = _quality_band(len(results), max_score)
    return ToolQualityMeta(
        scope_used=scope_used,
        search_type=search_type,
        result_count=len(results),
        max_score=max_score,
        quality_band=band,
        scope_relaxation_recommended=(scope_used == "document" and band != "high"),
    )


def _format_content(results: list[SearchResult]) -> str:
    if not results:
        return "No relevant knowledge-base evidence was found for the query."
    lines: list[str] = []
    for index, result in enumerate(results, start=1):
        title = str(result.get("title") or f"Document {index}")
        score = float(result.get("score", 0.0) or 0.0)
        text = str(result.get("text") or "").strip() or "No content available"
        lines.append(f"{index}. [{title}] (score: {score:.2f})")
        lines.append(f"   {text}")
    return "\n".join(lines)


def _to_sources(results: list[SearchResult]) -> list[SourceItem]:
    sources: list[SourceItem] = []
    for result in results:
        sources.append(
            SourceItem(
                document_id=str(result.get("document_id") or ""),
                chunk_id=str(result.get("chunk_id") or ""),
                title=str(result.get("title") or ""),
                text=str(result.get("text") or ""),
                score=float(result.get("score", 0.0) or 0.0),
                source_type=str(result.get("source_type") or "retrieval"),
            )
        )
    return sources


def _normalize_search_results(results: list[SearchResult]) -> list[SearchResult]:
    normalized: list[SearchResult] = []
    for item in results:
        normalized.append(
            {
                "document_id": str(item.get("document_id") or ""),
                "chunk_id": str(item.get("chunk_id") or ""),
                "title": str(item.get("title") or ""),
                "text": str(item.get("text") or ""),
                "score": float(item.get("score", 0.0) or 0.0),
                "source_type": str(item.get("source_type") or "retrieval"),
            }
        )
    return normalized


async def keyword_search_executor(
    payload: SearchPayload,
    *,
    index_name: str = "newbee_notebook_docs",
    es_url: str | None = None,
) -> list[SearchResult]:
    raw_results, _ = es_search_with_raw(
        query=payload["query"],
        index_name=index_name,
        max_results=int(payload["max_results"]),
        es_url=es_url,
        allowed_doc_ids=payload.get("allowed_document_ids"),
    )
    return _normalize_search_results(raw_results)


def _node_to_result(node_with_score: Any) -> SearchResult:
    node = getattr(node_with_score, "node", node_with_score)
    metadata = getattr(node, "metadata", {}) or {}
    inner_meta = {}
    raw_inner = metadata.get("_node_content")
    if isinstance(raw_inner, str):
        try:
            import json

            raw_inner = json.loads(raw_inner)
        except Exception:
            raw_inner = None
    if isinstance(raw_inner, dict):
        inner_meta = raw_inner.get("metadata") or {}
    title = (
        inner_meta.get("title")
        or metadata.get("title")
        or inner_meta.get("file_name")
        or metadata.get("file_name")
        or "Untitled"
    )
    text = ""
    get_content = getattr(node, "get_content", None)
    if callable(get_content):
        text = str(get_content()).strip()
    if not text:
        text = str(getattr(node, "text", "") or "").strip()
    return {
        "document_id": str(extract_document_id(node_with_score) or ""),
        "chunk_id": str(getattr(node, "node_id", "") or ""),
        "title": str(title),
        "text": text,
        "score": float(getattr(node_with_score, "score", 0.0) or 0.0),
        "source_type": "retrieval",
    }


async def semantic_search_executor(
    payload: SearchPayload,
    *,
    pgvector_index: Any,
) -> list[SearchResult]:
    pg_filters, _es_filters, allowed_doc_ids = build_document_filters(
        payload.get("allowed_document_ids")
    )
    base_retriever = pgvector_index.as_retriever(
        similarity_top_k=int(payload["max_results"]),
        filters=pg_filters,
    )
    scoped_retriever = ScopedRetriever(
        base_retriever=base_retriever,
        allowed_doc_ids=allowed_doc_ids,
        top_k=int(payload["max_results"]),
    )
    results = await scoped_retriever.aretrieve(QueryBundle(str(payload["query"])))
    return _normalize_search_results([_node_to_result(item) for item in results])


async def hybrid_search_executor(
    payload: SearchPayload,
    *,
    pgvector_index: Any,
    es_index: Any,
) -> list[SearchResult]:
    pg_filters, es_filters, allowed_doc_ids = build_document_filters(
        payload.get("allowed_document_ids")
    )
    retriever = build_hybrid_retriever(
        pgvector_index=pgvector_index,
        es_index=es_index,
        pgvector_top_k=int(payload["max_results"]),
        es_top_k=int(payload["max_results"]),
        final_top_k=int(payload["max_results"]),
        pg_filters=pg_filters,
        es_filters=es_filters,
        allowed_doc_ids=allowed_doc_ids,
    )
    results = await retriever.aretrieve(QueryBundle(str(payload["query"])))
    return _normalize_search_results([_node_to_result(item) for item in results])


def build_knowledge_base_tool(
    *,
    hybrid_search: SearchExecutor | None = None,
    semantic_search: SearchExecutor | None = None,
    keyword_search: SearchExecutor | None = None,
    allowed_document_ids: Sequence[str] | None = None,
    default_search_type: str = "hybrid",
    default_max_results: int = 5,
    description: str | None = None,
) -> ToolDefinition:
    executors: dict[str, SearchExecutor | None] = {
        "hybrid": hybrid_search,
        "semantic": semantic_search,
        "keyword": keyword_search,
    }

    async def _execute(payload: dict[str, Any]) -> ToolCallResult:
        query = str(payload.get("query") or "").strip()
        if not query:
            return ToolCallResult(content="", error="query is required")

        search_type = str(payload.get("search_type") or default_search_type).strip().lower()
        if search_type not in executors:
            return ToolCallResult(content="", error=f"unsupported search_type: {search_type}")

        max_results = int(payload.get("max_results") or default_max_results)
        scope_used, scoped_allowed = _resolve_scope(
            allowed_document_ids=payload.get("allowed_document_ids", allowed_document_ids),
            filter_document_id=payload.get("filter_document_id"),
        )
        normalized_payload: SearchPayload = {
            "query": query,
            "search_type": search_type,
            "max_results": max_results,
            "allowed_document_ids": scoped_allowed,
            "filter_document_id": payload.get("filter_document_id"),
        }

        if scoped_allowed == []:
            quality_meta = _build_quality_meta(
                scope_used=scope_used,
                search_type=search_type,
                results=[],
            )
            return ToolCallResult(
                content=_format_content([]),
                sources=[],
                quality_meta=quality_meta,
            )

        executor = executors[search_type]
        if executor is None:
            return ToolCallResult(content="", error=f"{search_type} search is not configured")

        results = _normalize_search_results(await executor(normalized_payload))
        quality_meta = _build_quality_meta(
            scope_used=scope_used,
            search_type=search_type,
            results=results,
        )
        return ToolCallResult(
            content=_format_content(results),
            sources=_to_sources(results),
            quality_meta=quality_meta,
        )

    return ToolDefinition(
        name="knowledge_base",
        description=description
        or (
            "Retrieve notebook or document-grounded knowledge. "
            "Use query for a precise retrieval phrase, search_type to choose keyword, semantic, "
            "or hybrid retrieval, max_results to control evidence breadth, and filter_document_id "
            "to stay inside one current document when needed. allowed_document_ids is injected by "
            "the runtime to enforce notebook scope; do not assume access outside it."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "A precise retrieval query built from the user's request and the most "
                        "important entities, phrases, or concepts. Avoid vague queries like "
                        "'document', '*' or a single generic noun when more specific wording exists."
                    ),
                },
                "search_type": {
                    "type": "string",
                    "enum": ["hybrid", "semantic", "keyword"],
                    "description": (
                        "Retrieval strategy. Use keyword for exact titles, names, quoted text, "
                        "or terminology; semantic for paraphrased concepts; hybrid for most "
                        "notebook question answering when both recall and precision matter."
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "description": (
                        "How many evidence chunks to retrieve. Keep it modest for focused lookup "
                        "(for example 3-5) and increase only when broader coverage is needed."
                    ),
                },
                "filter_document_id": {
                    "type": "string",
                    "description": (
                        "Optional current-document scope. Use this when the answer should stay "
                        "inside one specific document instead of the broader notebook scope."
                    ),
                },
            },
            "required": ["query"],
        },
        execute=_execute,
    )
