"""Zhipu web search tools """

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests

from newbee_notebook.core.common.config import get_zhipu_tools_config
from newbee_notebook.core.tools.contracts import SourceItem, ToolCallResult, ToolDefinition


DEFAULT_BASE_URL = "https://open.bigmodel.cn/api"


class ZhipuToolError(Exception):
    """Custom error for Zhipu tool failures."""


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


def zhipu_web_search(search_query: str, search_recency_filter: Optional[str] = None) -> str:
    """Use Zhipu Web Search to fetch web results."""
    if not search_query or not search_query.strip():
        raise ZhipuToolError("search_query is required.")

    cfg = _load_tool_config("web_search")
    api_key = _get_api_key()
    timeout = float(cfg.get("timeout", 30))

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

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        if not resp.ok:
            return f"Zhipu web_search request failed: HTTP {resp.status_code} - {resp.text}"
        data = resp.json()
        return _format_search_results(data)
    except Exception as exc:
        return f"Zhipu web_search request error: {exc}"


def zhipu_web_crawl(url: str, return_format: Optional[str] = None) -> str:
    """Use Zhipu Web Reader to fetch and parse a web page."""
    if not url or not url.strip():
        raise ZhipuToolError("url is required.")

    cfg = _load_tool_config("web_crawl")
    api_key = _get_api_key()
    timeout = float(cfg.get("timeout", 30))

    payload: Dict[str, Any] = {
        "url": url,
        "return_format": return_format or cfg.get("return_format", "markdown"),
        "retain_images": cfg.get("retain_images", True),
        "no_cache": cfg.get("no_cache", False),
        "timeout": int(cfg.get("timeout", 30)),
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

    try:
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
        if not resp.ok:
            return f"Zhipu web_crawl request failed: HTTP {resp.status_code} - {resp.text}"
        data = resp.json()
        return _format_reader_result(data)
    except Exception as exc:
        return f"Zhipu web_crawl request error: {exc}"


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
) -> ToolCallResult:
    if not search_query or not search_query.strip():
        return ToolCallResult(content="", error="search_query is required")

    content = zhipu_web_search(
        search_query=search_query,
        search_recency_filter=search_recency_filter,
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
) -> ToolCallResult:
    if not url or not url.strip():
        return ToolCallResult(content="", error="url is required")

    content = zhipu_web_crawl(url=url, return_format=return_format)
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
        return _zhipu_runtime_search(
            search_query=str(payload.get("search_query") or "").strip(),
            search_recency_filter=str(payload.get("search_recency_filter") or default_recency),
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
        return _zhipu_runtime_crawl(
            url=str(payload.get("url") or "").strip(),
            return_format=str(payload.get("return_format") or default_return_format),
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
