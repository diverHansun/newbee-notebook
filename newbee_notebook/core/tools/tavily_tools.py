"""Tavily web tools"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from typing import Literal, Optional

import requests

from newbee_notebook.core.tools.contracts import SourceItem, ToolCallResult, ToolDefinition

WEB_SEARCH_TIMEOUT_SECONDS = 10.0
WEB_CRAWL_TIMEOUT_SECONDS = 20.0
MAX_RETRIES = 1
RETRY_DELAY_SECONDS = 0.5


def _require_api_key() -> str:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY environment variable is not set.")
    return api_key


def _error_summary(exc: Exception, max_chars: int = 240) -> str:
    text = str(exc) or exc.__class__.__name__
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _status_code_from_exception(exc: Exception) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code
    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    if isinstance(response_status, int):
        return response_status
    return None


def _is_tavily_timeout_error(exc: Exception) -> bool:
    try:
        from tavily.errors import TimeoutError as TavilyTimeoutError
    except Exception:
        return False
    return isinstance(exc, TavilyTimeoutError)


def _is_retryable_exception(exc: Exception) -> bool:
    if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout, TimeoutError)):
        return True
    if _is_tavily_timeout_error(exc):
        return True
    status_code = _status_code_from_exception(exc)
    return status_code is not None and 500 <= status_code < 600


async def _call_with_retries(call: Callable[[], ToolCallResult]) -> ToolCallResult:
    for attempt in range(MAX_RETRIES + 1):
        try:
            return call()
        except Exception as exc:
            if not _is_retryable_exception(exc) or attempt >= MAX_RETRIES:
                raise
            await asyncio.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError("unreachable retry state")


def _with_execution_metadata(
    result: ToolCallResult,
    *,
    requested_provider: str,
    fallback_used: bool,
    fallback_error: Exception | None = None,
) -> ToolCallResult:
    metadata = dict(result.metadata)
    metadata["requested_provider"] = requested_provider
    metadata["fallback_used"] = fallback_used
    if fallback_error is not None:
        metadata["fallback_from_error"] = _error_summary(fallback_error)
    return ToolCallResult(
        content=result.content,
        sources=result.sources,
        images=result.images,
        quality_meta=result.quality_meta,
        metadata=metadata,
        error=result.error,
    )


def _format_results(response: dict, max_chars: int = 400) -> str:
    lines = []
    if response.get("answer"):
        lines.append(f"Summary: {response['answer']}\n")
    for i, res in enumerate(response.get("results", []), 1):
        title = res.get("title", "No title")
        url = res.get("url", "")
        content = (res.get("content") or "")[:max_chars]
        lines.append(f"{i}. {title}\n   URL: {url}\n   {content}...\n")
    return "\n".join(lines) if lines else "No results found."


def tavily_search(
    query: str,
    max_results: int = 5,
    search_depth: Literal["basic", "advanced", "fast", "ultra-fast"] = "advanced",
    topic: Literal["general", "news", "finance"] = "general",
    time_range: Optional[Literal["day", "week", "month", "year"]] = None,
    timeout: float = WEB_SEARCH_TIMEOUT_SECONDS,
) -> str:
    """General web search."""
    from tavily import TavilyClient

    client = TavilyClient(api_key=_require_api_key())
    resp = client.search(
        query=query,
        max_results=max_results,
        search_depth=search_depth,
        topic=topic,
        time_range=time_range,
        include_answer=True,
        include_raw_content=False,
        timeout=timeout,
    )
    return _format_results(resp)


def tavily_crawl(
    url: str,
    max_results: int = 1,
    include_raw_content: bool = False,
    include_images: bool = False,
    timeout: float = WEB_CRAWL_TIMEOUT_SECONDS,
) -> str:
    """Fetch and summarize content from a URL."""
    from tavily import TavilyClient

    client = TavilyClient(api_key=_require_api_key())
    resp = client.crawl(
        url=url,
        max_results=max_results,
        include_raw_content=include_raw_content,
        include_images=include_images,
        include_favicon=False,
        timeout=timeout,
    )
    results = resp.get("results", [])
    if not results:
        return "No content fetched."
    lines = []
    for i, item in enumerate(results, 1):
        title = item.get("title", url)
        content = (item.get("content") or "")[:800]
        lines.append(f"{i}. {title}\n{content}...\n")
    return "\n".join(lines)


def _build_source_item(title: str, content: str, locator: str, source_type: str = "web_search") -> SourceItem:
    return SourceItem(
        document_id="",
        chunk_id=locator,
        title=title,
        text=content,
        source_type=source_type,
    )


def _tavily_runtime_search(
    *,
    query: str,
    max_results: int = 5,
    search_depth: Literal["basic", "advanced", "fast", "ultra-fast"] = "advanced",
    topic: Literal["general", "news", "finance"] = "general",
    time_range: Optional[Literal["day", "week", "month", "year"]] = None,
    timeout: float = WEB_SEARCH_TIMEOUT_SECONDS,
) -> ToolCallResult:
    if not query or not query.strip():
        return ToolCallResult(content="", error="query is required")

    content = tavily_search(
        query=query,
        max_results=max_results,
        search_depth=search_depth,
        topic=topic,
        time_range=time_range,
        timeout=timeout,
    )
    return ToolCallResult(
        content=content,
        metadata={
            "provider": "tavily",
            "operation": "search",
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "topic": topic,
            "time_range": time_range,
        },
    )


def _tavily_runtime_crawl(
    *,
    url: str,
    max_results: int = 1,
    include_raw_content: bool = False,
    include_images: bool = False,
    timeout: float = WEB_CRAWL_TIMEOUT_SECONDS,
) -> ToolCallResult:
    if not url or not url.strip():
        return ToolCallResult(content="", error="url is required")

    content = tavily_crawl(
        url=url,
        max_results=max_results,
        include_raw_content=include_raw_content,
        include_images=include_images,
        timeout=timeout,
    )
    return ToolCallResult(
        content=content,
        sources=[_build_source_item(url, content, url)],
        metadata={
            "provider": "tavily",
            "operation": "crawl",
            "url": url,
            "max_results": max_results,
            "include_raw_content": include_raw_content,
            "include_images": include_images,
        },
    )


def build_tavily_search_runtime_tool(
    default_max_results: int = 5,
    default_search_depth: Literal["basic", "advanced", "fast", "ultra-fast"] = "advanced",
    default_topic: Literal["general", "news", "finance"] = "general",
) -> ToolDefinition:
    async def _execute(payload: dict) -> ToolCallResult:
        query = str(payload.get("query") or "").strip()
        max_results = int(payload.get("max_results") or default_max_results)
        search_depth = str(payload.get("search_depth") or default_search_depth)
        topic = str(payload.get("topic") or default_topic)
        time_range = payload.get("time_range")

        try:
            result = await _call_with_retries(
                lambda: _tavily_runtime_search(
                    query=query,
                    max_results=max_results,
                    search_depth=search_depth,
                    topic=topic,
                    time_range=time_range,
                    timeout=WEB_SEARCH_TIMEOUT_SECONDS,
                )
            )
            return _with_execution_metadata(
                result,
                requested_provider="tavily",
                fallback_used=False,
            )
        except Exception as exc:
            if not _is_retryable_exception(exc):
                return ToolCallResult(
                    content="",
                    error=f"web search failed: {_error_summary(exc)}",
                    metadata={
                        "provider": "tavily",
                        "operation": "search",
                        "requested_provider": "tavily",
                        "fallback_used": False,
                    },
                )
            primary_error = exc

        try:
            from newbee_notebook.core.tools.zhipu_tools import _zhipu_runtime_search

            result = _zhipu_runtime_search(
                search_query=query,
                search_recency_filter=None,
                timeout=WEB_SEARCH_TIMEOUT_SECONDS,
            )
            return _with_execution_metadata(
                result,
                requested_provider="tavily",
                fallback_used=True,
                fallback_error=primary_error,
            )
        except Exception as fallback_exc:
            return ToolCallResult(
                content="",
                error=(
                    "web search failed: "
                    f"tavily error: {_error_summary(primary_error)}; "
                    f"zhipu fallback error: {_error_summary(fallback_exc)}"
                ),
                metadata={
                    "provider": "tavily",
                    "operation": "search",
                    "requested_provider": "tavily",
                    "fallback_used": True,
                    "fallback_provider": "zhipu",
                },
            )

    return ToolDefinition(
        name="tavily_search",
        description=(
            "Search the public web for fresh external information. "
            "Use for current events, vendor documentation, product pages, pricing, or facts not present in notebook documents. "
            "Provide a precise query, keep max_results modest unless broader coverage is needed, and use topic to bias retrieval."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Precise web search query describing the target fact, entity, product, or topic.",
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "How many web search results to retrieve. Defaults to 5 and can be lowered for narrow lookups.",
                },
                "search_depth": {
                    "type": "string",
                    "enum": ["basic", "advanced", "fast", "ultra-fast"],
                    "description": "Search thoroughness and latency tradeoff. Advanced is the default balanced mode.",
                },
                "topic": {
                    "type": "string",
                    "enum": ["general", "news", "finance"],
                    "description": "Result domain bias. Use general unless the request is explicitly news- or finance-oriented.",
                },
                "time_range": {
                    "type": "string",
                    "enum": ["day", "week", "month", "year"],
                    "description": "Optional recency window for time-sensitive web search.",
                },
            },
            "required": ["query"],
        },
        execute=_execute,
    )


def build_tavily_crawl_runtime_tool(
    default_max_results: int = 1,
) -> ToolDefinition:
    async def _execute(payload: dict) -> ToolCallResult:
        url = str(payload.get("url") or "").strip()
        max_results = int(payload.get("max_results") or default_max_results)
        include_raw_content = bool(payload.get("include_raw_content", False))
        include_images = bool(payload.get("include_images", False))

        try:
            result = await _call_with_retries(
                lambda: _tavily_runtime_crawl(
                    url=url,
                    max_results=max_results,
                    include_raw_content=include_raw_content,
                    include_images=include_images,
                    timeout=WEB_CRAWL_TIMEOUT_SECONDS,
                )
            )
            return _with_execution_metadata(
                result,
                requested_provider="tavily",
                fallback_used=False,
            )
        except Exception as exc:
            if not _is_retryable_exception(exc):
                return ToolCallResult(
                    content="",
                    error=f"web crawl failed: {_error_summary(exc)}",
                    metadata={
                        "provider": "tavily",
                        "operation": "crawl",
                        "requested_provider": "tavily",
                        "fallback_used": False,
                    },
                )
            primary_error = exc

        try:
            from newbee_notebook.core.tools.zhipu_tools import _zhipu_runtime_crawl

            result = _zhipu_runtime_crawl(
                url=url,
                return_format=None,
                timeout=WEB_CRAWL_TIMEOUT_SECONDS,
            )
            return _with_execution_metadata(
                result,
                requested_provider="tavily",
                fallback_used=True,
                fallback_error=primary_error,
            )
        except Exception as fallback_exc:
            return ToolCallResult(
                content="",
                error=(
                    "web crawl failed: "
                    f"tavily error: {_error_summary(primary_error)}; "
                    f"zhipu fallback error: {_error_summary(fallback_exc)}"
                ),
                metadata={
                    "provider": "tavily",
                    "operation": "crawl",
                    "requested_provider": "tavily",
                    "fallback_used": True,
                    "fallback_provider": "zhipu",
                },
            )

    return ToolDefinition(
        name="tavily_crawl",
        description=(
            "Fetch and summarize the contents of a specific web page URL. "
            "Use after search when a target page should be read more directly."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The target web page URL to fetch and summarize.",
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Maximum number of crawl results to return. Defaults to 1 for a single page lookup.",
                },
                "include_raw_content": {
                    "type": "boolean",
                    "description": "Whether to include raw page content when available. Defaults to false.",
                },
                "include_images": {
                    "type": "boolean",
                    "description": "Whether to include image references when available. Defaults to false.",
                },
            },
            "required": ["url"],
        },
        execute=_execute,
    )
