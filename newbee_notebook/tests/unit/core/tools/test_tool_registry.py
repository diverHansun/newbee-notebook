from __future__ import annotations

from newbee_notebook.core.tools.builtin_provider import BuiltinToolProvider
from newbee_notebook.core.tools.contracts import ToolDefinition, ToolCallResult
from newbee_notebook.core.tools.registry import ToolRegistry


async def _fake_tool_result(_: dict) -> ToolCallResult:
    return ToolCallResult(content="ok")


def _external_tool(name: str) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"{name} tool",
        parameters={"type": "object", "properties": {}},
        execute=_fake_tool_result,
    )


def test_builtin_tool_provider_returns_ask_tools():
    provider = BuiltinToolProvider()

    tools = provider.get_tools("ask")

    assert [tool.name for tool in tools] == ["knowledge_base", "time"]


def test_builtin_tool_provider_returns_explain_and_conclude_as_knowledge_base_only():
    provider = BuiltinToolProvider()

    explain_tools = provider.get_tools("explain")
    conclude_tools = provider.get_tools("conclude")

    assert [tool.name for tool in explain_tools] == ["knowledge_base"]
    assert [tool.name for tool in conclude_tools] == ["knowledge_base"]


def test_tool_registry_merges_external_agent_tools_without_changing_contract():
    registry = ToolRegistry(builtin_provider=BuiltinToolProvider())

    tools = registry.get_tools("agent", external_tools=[_external_tool("mcp.search")])

    assert [tool.name for tool in tools] == ["knowledge_base", "time", "mcp.search"]
    assert all(isinstance(tool, ToolDefinition) for tool in tools)
