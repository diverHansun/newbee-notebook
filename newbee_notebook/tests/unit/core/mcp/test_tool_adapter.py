from __future__ import annotations

import pytest

from newbee_notebook.core.mcp.tool_adapter import MCPToolAdapter
from newbee_notebook.core.mcp.types import MCPToolInfo


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_mcp_tool_adapter_prefixes_server_name_and_routes_call():
    captured: list[tuple[str, dict]] = []

    async def _invoke(tool_name: str, arguments: dict):
        captured.append((tool_name, dict(arguments)))
        return {
            "content": [
                {"type": "text", "text": "sunny"},
                {"type": "image", "url": "ignored"},
            ]
        }

    tool = MCPToolAdapter.adapt(
        MCPToolInfo(
            server_name="weather",
            name="forecast",
            qualified_name="weather_forecast",
            description="Get weather forecast",
            input_schema={"type": "object", "properties": {"city": {"type": "string"}}},
        ),
        invoke_tool=_invoke,
    )

    result = await tool.execute({"city": "Hong Kong"})

    assert tool.name == "weather_forecast"
    assert tool.parameters["type"] == "object"
    assert captured == [("forecast", {"city": "Hong Kong"})]
    assert result.content == "sunny"
    assert result.error is None
    assert result.sources == []
    assert result.metadata["server_name"] == "weather"


def test_mcp_tool_adapter_converts_mixed_content_and_errors():
    result = MCPToolAdapter.convert_response(
        {
            "isError": True,
            "content": [
                {"type": "text", "text": "tool failed"},
                {"type": "resource", "uri": "ignored"},
            ],
        }
    )

    assert result.content == "tool failed"
    assert result.error == "tool failed"
