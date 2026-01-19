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
        description="General web search to retrieve fresh information; supports general/news/finance topics.",
    )


def build_tavily_news_tool(max_results: int = 5) -> FunctionTool:
    return FunctionTool.from_defaults(
        fn=lambda query: tavily_news_search(query=query, max_results=max_results),
        name="tavily_news",
        description="News-focused search for recent reports and summaries.",
    )


def build_tavily_crawl_tool(max_results: int = 1) -> FunctionTool:
    return FunctionTool.from_defaults(
        fn=lambda url: tavily_crawl(url=url, max_results=max_results),
        name="tavily_crawl",
        description="Fetch and summarize the main content of a given URL.",
    )


# ---------------------------------------------------------------------------
# Simple OO wrapper used by tests
# ---------------------------------------------------------------------------


class TavilySearchTool:
    """Wrapper exposing Tavily search as a FunctionTool (cached)."""

    def __init__(self, max_results: int = 5):
        self.max_results = max_results
        self._function_tool: FunctionTool | None = None

    def _ensure_api_key(self) -> None:
        if not os.getenv("TAVILY_API_KEY"):
            raise ValueError("TAVILY_API_KEY not set")

    def get_tool(self) -> FunctionTool:
        if self._function_tool is None:
            self._ensure_api_key()
            self._function_tool = FunctionTool.from_defaults(
                fn=lambda query: tavily_search(query=query, max_results=self.max_results),
                name="web_search",
                description="Web search using Tavily; retrieves fresh results.",
            )
        return self._function_tool


def build_tavily_tool(max_results: int = 5) -> FunctionTool:
    """Convenience function matching legacy tests."""
    return TavilySearchTool(max_results=max_results).get_tool()


