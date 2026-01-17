"""Tool registry builder for chat/agent modes."""

from typing import List, Optional
import os
from llama_index.core.tools import BaseTool
from src.tools.tavily import (
    build_tavily_search_tool,
    build_tavily_news_tool,
    build_tavily_crawl_tool,
)
from src.tools.es_search_tool import build_es_search_tool
from src.tools.zhipu_tools import (
    build_zhipu_web_search_tool,
    build_zhipu_web_crawl_tool,
)
from src.common.config import get_zhipu_tools_config
from src.tools.time import build_current_time_tool


def build_tool_registry(es_index_name: Optional[str] = None) -> List[BaseTool]:
    """Build the list of enabled tools based on env/config.

    Args:
        es_index_name: Optional ES index name for knowledge-base search tool.
    """
    tools: List[BaseTool] = []

    # Always provide current time tool
    try:
        tools.append(build_current_time_tool())
        print("[Tools] current_time tool enabled")
    except Exception as e:
        print(f"[Tools] Warning: Failed to initialize current_time tool: {e}")

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

    # Enable Zhipu tools when API key and config allow
    if os.getenv("ZHIPU_API_KEY"):
        zhipu_cfg = get_zhipu_tools_config() or {}
        zhipu_tools = zhipu_cfg.get("zhipu_tools", {}) or {}
        web_search_cfg = zhipu_tools.get("web_search", {}) or {}
        web_crawl_cfg = zhipu_tools.get("web_crawl", {}) or {}

        if web_search_cfg.get("enabled", False):
            try:
                tools.append(build_zhipu_web_search_tool())
                print("[Tools] Zhipu web_search enabled")
            except Exception as e:
                print(f"[Tools] Warning: Failed to initialize Zhipu web_search: {e}")

        if web_crawl_cfg.get("enabled", False):
            try:
                tools.append(build_zhipu_web_crawl_tool())
                print("[Tools] Zhipu web_crawl enabled")
            except Exception as e:
                print(f"[Tools] Warning: Failed to initialize Zhipu web_crawl: {e}")

    return tools
