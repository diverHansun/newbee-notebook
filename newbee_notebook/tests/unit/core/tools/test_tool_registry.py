from __future__ import annotations

import pytest

from newbee_notebook.core.tools.builtin_provider import BuiltinToolProvider
from newbee_notebook.core.tools.contracts import ToolDefinition, ToolCallResult
from newbee_notebook.core.tools.registry import ToolRegistry


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def _fake_tool_result(_: dict) -> ToolCallResult:
    return ToolCallResult(content="ok")


def _external_tool(name: str) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"{name} tool",
        parameters={"type": "object", "properties": {}},
        execute=_fake_tool_result,
    )


def test_builtin_tool_provider_returns_ask_tools(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
    provider = BuiltinToolProvider()

    tools = provider.get_tools("ask")

    assert [tool.name for tool in tools] == ["knowledge_base", "time"]


def test_builtin_tool_provider_returns_explain_and_conclude_as_knowledge_base_only(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
    provider = BuiltinToolProvider()

    explain_tools = provider.get_tools("explain")
    conclude_tools = provider.get_tools("conclude")

    assert [tool.name for tool in explain_tools] == ["knowledge_base"]
    assert [tool.name for tool in conclude_tools] == ["knowledge_base"]


@pytest.mark.anyio
async def test_tool_registry_merges_external_agent_tools_without_changing_contract(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
    registry = ToolRegistry(builtin_provider=BuiltinToolProvider())

    tools = await registry.get_tools("agent", external_tools=[_external_tool("mcp.search")])

    assert [tool.name for tool in tools] == ["knowledge_base", "time", "mcp.search"]
    assert all(isinstance(tool, ToolDefinition) for tool in tools)


@pytest.mark.anyio
async def test_tool_registry_merges_external_ask_tools_without_changing_contract(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
    registry = ToolRegistry(builtin_provider=BuiltinToolProvider())

    tools = await registry.get_tools("ask", external_tools=[_external_tool("image_generate")])

    assert [tool.name for tool in tools] == ["knowledge_base", "time", "image_generate"]
    assert all(isinstance(tool, ToolDefinition) for tool in tools)


@pytest.mark.anyio
async def test_tool_registry_reads_cached_mcp_tools_for_agent_only(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
    registry = ToolRegistry(
        builtin_provider=BuiltinToolProvider(),
        mcp_tool_supplier=lambda: [_external_tool("weather_forecast")],
    )

    agent_tools = await registry.get_tools("agent")
    ask_tools = await registry.get_tools("ask")

    assert [tool.name for tool in agent_tools] == ["knowledge_base", "time", "weather_forecast"]
    assert [tool.name for tool in ask_tools] == ["knowledge_base", "time"]


@pytest.mark.anyio
async def test_tool_registry_awaits_async_mcp_supplier_for_agent_only(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
    supplier_calls: list[str] = []

    async def _supplier():
        supplier_calls.append("agent")
        return [_external_tool("filesystem_read_file")]

    registry = ToolRegistry(
        builtin_provider=BuiltinToolProvider(),
        mcp_tool_supplier=_supplier,
    )

    agent_tools = await registry.get_tools("agent")
    explain_tools = await registry.get_tools("explain")

    assert [tool.name for tool in agent_tools] == ["knowledge_base", "time", "filesystem_read_file"]
    assert [tool.name for tool in explain_tools] == ["knowledge_base"]
    assert supplier_calls == ["agent"]
