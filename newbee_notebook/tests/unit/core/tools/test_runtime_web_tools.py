from __future__ import annotations

import pytest

from newbee_notebook.core.tools.builtin_provider import BuiltinToolProvider
from newbee_notebook.core.tools.tavily_tools import build_tavily_search_runtime_tool, build_tavily_crawl_runtime_tool
from newbee_notebook.core.tools.zhipu_tools import build_zhipu_web_search_runtime_tool, build_zhipu_web_crawl_runtime_tool


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_builtin_tool_provider_adds_web_tools_to_agent_when_api_keys_are_present(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily")
    monkeypatch.setenv("ZHIPU_API_KEY", "test-zhipu")

    provider = BuiltinToolProvider()

    tools = provider.get_tools("agent")

    assert [tool.name for tool in tools] == [
        "knowledge_base",
        "time",
        "tavily_search",
        "tavily_crawl",
        "zhipu_web_search",
        "zhipu_web_crawl",
    ]


def test_builtin_tool_provider_keeps_ask_and_reader_modes_grounded_even_with_api_keys(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily")
    monkeypatch.setenv("ZHIPU_API_KEY", "test-zhipu")

    provider = BuiltinToolProvider()

    assert [tool.name for tool in provider.get_tools("ask")] == ["knowledge_base", "time"]
    assert [tool.name for tool in provider.get_tools("explain")] == ["knowledge_base"]
    assert [tool.name for tool in provider.get_tools("conclude")] == ["knowledge_base"]


def test_builtin_tool_provider_only_injects_web_tools_with_available_credentials(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setenv("ZHIPU_API_KEY", "test-zhipu")

    provider = BuiltinToolProvider()

    tools = provider.get_tools("agent")

    assert [tool.name for tool in tools] == [
        "knowledge_base",
        "time",
        "zhipu_web_search",
        "zhipu_web_crawl",
    ]


def test_tavily_runtime_tools_expose_openai_compatible_parameter_schema():
    search_tool = build_tavily_search_runtime_tool()
    crawl_tool = build_tavily_crawl_runtime_tool()

    assert search_tool.parameters["required"] == ["query"]
    assert "description" in search_tool.parameters["properties"]["query"]
    assert "max_results" in search_tool.parameters["properties"]
    assert crawl_tool.parameters["required"] == ["url"]
    assert "description" in crawl_tool.parameters["properties"]["url"]


def test_zhipu_runtime_tools_expose_openai_compatible_parameter_schema():
    search_tool = build_zhipu_web_search_runtime_tool()
    crawl_tool = build_zhipu_web_crawl_runtime_tool()

    assert search_tool.parameters["required"] == ["search_query"]
    assert "description" in search_tool.parameters["properties"]["search_query"]
    assert "search_recency_filter" in search_tool.parameters["properties"]
    assert crawl_tool.parameters["required"] == ["url"]
    assert "return_format" in crawl_tool.parameters["properties"]


@pytest.mark.anyio
async def test_runtime_web_tools_wrap_results_into_tool_call_result(monkeypatch):
    monkeypatch.setattr(
        "newbee_notebook.core.tools.tavily_tools.tavily_search",
        lambda query, max_results=5, search_depth="advanced", topic="general", time_range=None: "1. Result\\n   URL: https://example.com\\n   snippet",
    )
    monkeypatch.setattr(
        "newbee_notebook.core.tools.zhipu_tools.zhipu_web_search",
        lambda search_query, search_recency_filter=None: "1. Zhipu Result\\n   URL: https://zhipu.example\\n   Source: web\\n   snippet",
    )

    tavily_tool = build_tavily_search_runtime_tool()
    zhipu_tool = build_zhipu_web_search_runtime_tool()

    tavily_result = await tavily_tool.execute({"query": "firecrawl pricing"})
    zhipu_result = await zhipu_tool.execute({"search_query": "firecrawl pricing"})

    assert tavily_result.error is None
    assert tavily_result.content.startswith("1. Result")
    assert tavily_result.metadata["provider"] == "tavily"
    assert zhipu_result.error is None
    assert zhipu_result.content.startswith("1. Zhipu Result")
    assert zhipu_result.metadata["provider"] == "zhipu"
