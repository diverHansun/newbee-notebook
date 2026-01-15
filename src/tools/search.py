"""Search tool utilities (factory)."""

from typing import List, Optional
import os
from llama_index.core.tools import BaseTool
from src.tools.tavily import (
    build_tavily_search_tool,
    build_tavily_news_tool,
    build_tavily_crawl_tool,
)
from src.tools.es_search_tool import build_es_search_tool


def get_search_tools(es_index_name: Optional[str] = None) -> List[BaseTool]:
    """Get enabled search tools based on env configuration.

    Args:
        es_index_name: Optional ES index name for knowledge-base search tool.
    """
    tools: List[BaseTool] = []

    if os.getenv("TAVILY_API_KEY"):
        try:
            tools.append(build_tavily_search_tool())
            tools.append(build_tavily_news_tool())
            tools.append(build_tavily_crawl_tool())
            print("[Tools] Tavily web search/news/crawl enabled")
        except Exception as e:
            print(f"[Tools] Warning: Failed to initialize Tavily tools: {e}")

    # Enable ES BM25 tool when Elasticsearch URL is configured
    es_url = os.getenv("ELASTICSEARCH_URL", None)
    if es_url:
        try:
            tools.append(
                build_es_search_tool(
                    index_name=es_index_name or "medimind_docs",
                    es_url=es_url,
                )
            )
            print("[Tools] Elasticsearch knowledge_base_search enabled for Chat")
        except Exception as e:
            print(f"[Tools] Warning: Failed to initialize Elasticsearch tool: {e}")

    return tools
