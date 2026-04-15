"""Zhipu web search tools """

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from typing import Any, Dict, Optional

import requests

from newbee_notebook.core.common.config import get_zhipu_tools_config
from newbee_notebook.core.tools.contracts import SourceItem, ToolCallResult, ToolDefinition


DEFAULT_BASE_URL = "https://open.bigmodel.cn/api"
WEB_SEARCH_TIMEOUT_SECONDS = 10.0
WEB_CRAWL_TIMEOUT_SECONDS = 20.0
MAX_RETRIES = 1
RETRY_DELAY_SECONDS = 0.5


class ZhipuToolError(Exception):
    """Custom error for Zhipu tool failures."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


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


def _is_retryable_exception(exc: Exception) -> bool:
    if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout, TimeoutError)):
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


def _get_api_key() -> str:
    api_key = os.getenv("ZHIPU_API_KEY")
    if not api_key:
        raise ZhipuToolError("ZHIPU_API_KEY is not set.")
    return api_key


def _load_tool_config(section: str) -> Dict[str, Any]:
    cfg = get_zhipu_tools_config() or {}
    return (cfg.get("zhipu_tools", {}) or {}).get(section, {}) or {}


def _build_base_url(cfg: Dict[str, Any], path: str) -> str:
    base = cfg.get("base_url") or DEFAULT_BASE_URL
    return f"{base.rstrip('/')}{path}"


def _format_search_results(payload: Dict[str, Any]) -> str:
    intent = payload.get("search_intent") or []
    results = payload.get("search_result") or []
    lines = []

    if intent:
        intents = []
        for item in intent:
            intent_val = item.get("intent")
            keywords = item.get("keywords")
            if intent_val:
                intents.append(f"intent={intent_val} keywords={keywords or ''}".strip())
        if intents:
            lines.append("Search intent: " + "; ".join(intents))

    if not results:
        lines.append("No search results returned.")
        return "\n".join(lines)

    for idx, item in enumerate(results, 1):
        title = item.get("title") or "No title"
        link = item.get("link") or ""
        content = item.get("content") or ""
        media = item.get("media") or ""
        lines.append(f"{idx}. {title}\n   URL: {link}\n   Source: {media}\n   {content}".strip())
    return "\n".join(lines)


def _format_reader_result(payload: Dict[str, Any]) -> str:
    reader_result = payload.get("reader_result") or {}
    title = reader_result.get("title") or reader_result.get("url") or "Content"
    description = reader_result.get("description") or ""
    content = reader_result.get("content") or ""
    lines = [f"Title: {title}"]
    if description:
        lines.append(f"Description: {description}")
    if content:
        lines.append(content)
    else:
        lines.append("No content returned.")
    return "\n".join(lines)


def zhipu_web_search(
    search_query: str,
    search_recency_filter: Optional[str] = None,
    timeout: float | None = None,
) -> str:
    """Use Zhipu Web Search to fetch web results."""
    if not search_query or not search_query.strip():
        raise ZhipuToolError("search_query is required.")

    cfg = _load_tool_config("web_search")
    api_key = _get_api_key()
    request_timeout = float(timeout if timeout is not None else cfg.get("timeout", 30))

    payload: Dict[str, Any] = {
        "search_query": search_query,
        "search_engine": cfg.get("search_engine", "search_pro"),
        "search_intent": cfg.get("search_intent", False),
        "count": int(cfg.get("count", 10)),
        "search_recency_filter": search_recency_filter or cfg.get("search_recency_filter", "noLimit"),
        "content_size": cfg.get("content_size", "medium"),
    }

    url = _build_base_url(cfg, "/paas/v4/web_search")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=request_timeout)
    if not resp.ok:
        raise ZhipuToolError(
            f"HTTP {resp.status_code} - {resp.text}",
            status_code=resp.status_code,
        )
    data = resp.json()
    return _format_search_results(data)


def zhipu_web_crawl(
    url: str,
    return_format: Optional[str] = None,
    timeout: float | None = None,
) -> str:
    """Use Zhipu Web Reader to fetch and parse a web page."""
    if not url or not url.strip():
        raise ZhipuToolError("url is required.")

    cfg = _load_tool_config("web_crawl")
    api_key = _get_api_key()
    request_timeout = float(timeout if timeout is not None else cfg.get("timeout", 30))

    payload: Dict[str, Any] = {
        "url": url,
        "return_format": return_format or cfg.get("return_format", "markdown"),
        "retain_images": cfg.get("retain_images", True),
        "no_cache": cfg.get("no_cache", False),
        "timeout": int(request_timeout),
        "no_gfm": cfg.get("no_gfm", False),
        "keep_img_data_url": cfg.get("keep_img_data_url", False),
        "with_images_summary": cfg.get("with_images_summary", False),
        "with_links_summary": cfg.get("with_links_summary", False),
    }

    endpoint = _build_base_url(cfg, "/paas/v4/reader")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = requests.post(endpoint, json=payload, headers=headers, timeout=request_timeout)
    if not resp.ok:
        raise ZhipuToolError(
            f"HTTP {resp.status_code} - {resp.text}",
            status_code=resp.status_code,
        )
    data = resp.json()
    return _format_reader_result(data)


def _build_source_item(title: str, content: str, locator: str, source_type: str = "web_search") -> SourceItem:
    return SourceItem(
        document_id="",
        chunk_id=locator,
        title=title,
        text=content,
        source_type=source_type,
    )


def _zhipu_runtime_search(
    *,
    search_query: str,
    search_recency_filter: Optional[str] = None,
    timeout: float = WEB_SEARCH_TIMEOUT_SECONDS,
) -> ToolCallResult:
    if not search_query or not search_query.strip():
        return ToolCallResult(content="", error="search_query is required")

    content = zhipu_web_search(
        search_query=search_query,
        search_recency_filter=search_recency_filter,
        timeout=timeout,
    )
    return ToolCallResult(
        content=content,
        metadata={
            "provider": "zhipu",
            "operation": "search",
            "search_query": search_query,
            "search_recency_filter": search_recency_filter,
        },
    )


def _zhipu_runtime_crawl(
    *,
    url: str,
    return_format: Optional[str] = None,
    timeout: float = WEB_CRAWL_TIMEOUT_SECONDS,
) -> ToolCallResult:
    if not url or not url.strip():
        return ToolCallResult(content="", error="url is required")

    content = zhipu_web_crawl(url=url, return_format=return_format, timeout=timeout)
    return ToolCallResult(
        content=content,
        sources=[_build_source_item(url, content, url)],
        metadata={
            "provider": "zhipu",
            "operation": "crawl",
            "url": url,
            "return_format": return_format,
        },
    )


def build_zhipu_web_search_runtime_tool() -> ToolDefinition:
    cfg = _load_tool_config("web_search")
    default_recency = cfg.get("search_recency_filter", "noLimit")

    async def _execute(payload: dict) -> ToolCallResult:
        search_query = str(payload.get("search_query") or "").strip()
        search_recency_filter = str(payload.get("search_recency_filter") or default_recency)

        try:
            result = await _call_with_retries(
                lambda: _zhipu_runtime_search(
                    search_query=search_query,
                    search_recency_filter=search_recency_filter,
                    timeout=WEB_SEARCH_TIMEOUT_SECONDS,
                )
            )
            return _with_execution_metadata(
                result,
                requested_provider="zhipu",
                fallback_used=False,
            )
        except Exception as exc:
            if not _is_retryable_exception(exc):
                return ToolCallResult(
                    content="",
                    error=f"web search failed: {_error_summary(exc)}",
                    metadata={
                        "provider": "zhipu",
                        "operation": "search",
                        "requested_provider": "zhipu",
                        "fallback_used": False,
                    },
                )
            primary_error = exc

        try:
            from newbee_notebook.core.tools.tavily_tools import _tavily_runtime_search

            result = _tavily_runtime_search(
                query=search_query,
                max_results=5,
                timeout=WEB_SEARCH_TIMEOUT_SECONDS,
            )
            return _with_execution_metadata(
                result,
                requested_provider="zhipu",
                fallback_used=True,
                fallback_error=primary_error,
            )
        except Exception as fallback_exc:
            return ToolCallResult(
                content="",
                error=(
                    "web search failed: "
                    f"zhipu error: {_error_summary(primary_error)}; "
                    f"tavily fallback error: {_error_summary(fallback_exc)}"
                ),
                metadata={
                    "provider": "zhipu",
                    "operation": "search",
                    "requested_provider": "zhipu",
                    "fallback_used": True,
                    "fallback_provider": "tavily",
                },
            )

    return ToolDefinition(
        name="zhipu_web_search",
        description=(
            "Search the public web with Zhipu Web Search. "
            "Use for current external facts, product pages, official announcements, and sources outside notebook documents."
        ),
        parameters={
            "type": "object",
            "properties": {
                "search_query": {
                    "type": "string",
                    "description": "Precise web search query for the information that should be found outside the notebook.",
                },
                "search_recency_filter": {
                    "type": "string",
                    "enum": ["oneDay", "oneWeek", "oneMonth", "oneYear", "noLimit"],
                    "description": "Optional recency filter. Defaults to the configured search_recency_filter value.",
                },
            },
            "required": ["search_query"],
        },
        execute=_execute,
    )


def build_zhipu_web_crawl_runtime_tool() -> ToolDefinition:
    cfg = _load_tool_config("web_crawl")
    default_return_format = cfg.get("return_format", "markdown")

    async def _execute(payload: dict) -> ToolCallResult:
        url = str(payload.get("url") or "").strip()
        return_format = str(payload.get("return_format") or default_return_format)

        try:
            result = await _call_with_retries(
                lambda: _zhipu_runtime_crawl(
                    url=url,
                    return_format=return_format,
                    timeout=WEB_CRAWL_TIMEOUT_SECONDS,
                )
            )
            return _with_execution_metadata(
                result,
                requested_provider="zhipu",
                fallback_used=False,
            )
        except Exception as exc:
            if not _is_retryable_exception(exc):
                return ToolCallResult(
                    content="",
                    error=f"web crawl failed: {_error_summary(exc)}",
                    metadata={
                        "provider": "zhipu",
                        "operation": "crawl",
                        "requested_provider": "zhipu",
                        "fallback_used": False,
                    },
                )
            primary_error = exc

        try:
            from newbee_notebook.core.tools.tavily_tools import _tavily_runtime_crawl

            result = _tavily_runtime_crawl(
                url=url,
                max_results=1,
                timeout=WEB_CRAWL_TIMEOUT_SECONDS,
            )
            return _with_execution_metadata(
                result,
                requested_provider="zhipu",
                fallback_used=True,
                fallback_error=primary_error,
            )
        except Exception as fallback_exc:
            return ToolCallResult(
                content="",
                error=(
                    "web crawl failed: "
                    f"zhipu error: {_error_summary(primary_error)}; "
                    f"tavily fallback error: {_error_summary(fallback_exc)}"
                ),
                metadata={
                    "provider": "zhipu",
                    "operation": "crawl",
                    "requested_provider": "zhipu",
                    "fallback_used": True,
                    "fallback_provider": "tavily",
                },
            )

    return ToolDefinition(
        name="zhipu_web_crawl",
        description=(
            "Fetch and parse a specific web page using Zhipu Web Reader. "
            "Use after search when the target page should be read directly."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The target web page URL to fetch and parse.",
                },
                "return_format": {
                    "type": "string",
                    "enum": ["markdown", "text"],
                    "description": "Preferred returned content format. Defaults to the configured reader format.",
                },
            },
            "required": ["url"],
        },
        execute=_execute,
    )
