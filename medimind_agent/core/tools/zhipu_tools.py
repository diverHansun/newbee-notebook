"""Zhipu web search and web reader tools."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests
from llama_index.core.tools import FunctionTool

from medimind_agent.core.common.config import get_zhipu_tools_config


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


def build_zhipu_web_search_tool() -> FunctionTool:
    return FunctionTool.from_defaults(
        fn=zhipu_web_search,
        name="zhipu_web_search",
        description=(
            "Use Zhipu Web Search to fetch web results (title/URL/summary). "
            "Parameters: search_query (required), search_recency_filter "
            "(oneDay|oneWeek|oneMonth|oneYear|noLimit, defaults from config). "
            "Other search options use config defaults."
        ),
    )


def build_zhipu_web_crawl_tool() -> FunctionTool:
    return FunctionTool.from_defaults(
        fn=zhipu_web_crawl,
        name="zhipu_web_crawl",
        description=(
            "Use Zhipu Web Reader to fetch and parse a web page. "
            "Parameters: url (required), return_format (markdown|text, default from config). "
            "Other reader options use config defaults."
        ),
    )


