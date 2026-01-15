"""Tavily web tools (OpenAI-style tools for search, news, and URL crawl)."""

import os
from typing import Optional, Sequence, Literal

from llama_index.core.tools import FunctionTool, ToolMetadata


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


def tavily_news_search(
    query: str,
    max_results: int = 5,
    time_range: Literal["day", "week", "month", "year"] = "week",
) -> str:
    """News-focused search."""
    return tavily_search(
        query=query,
        max_results=max_results,
        search_depth="advanced",
        topic="news",
        time_range=time_range,
    )


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


def build_tavily_search_tool(max_results: int = 5) -> FunctionTool:
    return FunctionTool.from_defaults(
        fn=lambda query: tavily_search(query=query, max_results=max_results),
        name="tavily_search",
        description="通用网页搜索，用于获取最新信息/常规查询。",
    )


def build_tavily_news_tool(max_results: int = 5) -> FunctionTool:
    return FunctionTool.from_defaults(
        fn=lambda query: tavily_news_search(query=query, max_results=max_results),
        name="tavily_news",
        description="新闻搜索，获取最近新闻报道与摘要。",
    )


def build_tavily_crawl_tool(max_results: int = 1) -> FunctionTool:
    return FunctionTool.from_defaults(
        fn=lambda url: tavily_crawl(url=url, max_results=max_results),
        name="tavily_crawl",
        description="抓取指定 URL 内容，返回页面主要文本。",
    )
