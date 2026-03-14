"""Tavily web tools"""

from __future__ import annotations

import os
from typing import Literal, Optional

from newbee_notebook.core.tools.contracts import SourceItem, ToolCallResult, ToolDefinition


def _require_api_key() -> str:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY environment variable is not set.")
    return api_key


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
    )
    return _format_results(resp)


def tavily_crawl(
    url: str,
    max_results: int = 1,
    include_raw_content: bool = False,
    include_images: bool = False,
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
) -> ToolCallResult:
    if not query or not query.strip():
        return ToolCallResult(content="", error="query is required")

    content = tavily_search(
        query=query,
        max_results=max_results,
        search_depth=search_depth,
        topic=topic,
        time_range=time_range,
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
) -> ToolCallResult:
    if not url or not url.strip():
        return ToolCallResult(content="", error="url is required")

    content = tavily_crawl(
        url=url,
        max_results=max_results,
        include_raw_content=include_raw_content,
        include_images=include_images,
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
        return _tavily_runtime_search(
            query=str(payload.get("query") or "").strip(),
            max_results=int(payload.get("max_results") or default_max_results),
            search_depth=str(payload.get("search_depth") or default_search_depth),
            topic=str(payload.get("topic") or default_topic),
            time_range=payload.get("time_range"),
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
        return _tavily_runtime_crawl(
            url=str(payload.get("url") or "").strip(),
            max_results=int(payload.get("max_results") or default_max_results),
            include_raw_content=bool(payload.get("include_raw_content", False)),
            include_images=bool(payload.get("include_images", False)),
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
