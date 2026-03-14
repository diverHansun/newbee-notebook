from __future__ import annotations

import json
from pathlib import Path

import pytest

from newbee_notebook.core.mcp.client_manager import MCPClientManager
from newbee_notebook.core.mcp.types import MCPServerConfig, MCPToolInfo


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeClient:
    def __init__(self, server_name: str, tools: list[MCPToolInfo]):
        self.server_name = server_name
        self.tools = list(tools)
        self.closed = False

    async def list_tools(self) -> list[MCPToolInfo]:
        return list(self.tools)

    async def call_tool(self, tool_name: str, arguments: dict):
        return {"content": [{"type": "text", "text": f"{self.server_name}:{tool_name}:{arguments.get('q', '')}"}]}

    async def close(self) -> None:
        self.closed = True


@pytest.mark.anyio
async def test_client_manager_loads_enabled_servers_caches_tools_and_skips_disabled(tmp_path: Path):
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "weather": {"command": "python", "args": ["-m", "weather_server"]},
                    "notes": {"type": "http", "url": "https://example.com/mcp"},
                }
            }
        ),
        encoding="utf-8",
    )

    connect_calls: list[str] = []

    async def _connector(config: MCPServerConfig):
        connect_calls.append(config.name)
        return _FakeClient(
            config.name,
            [
                MCPToolInfo(
                    server_name=config.name,
                    name="search",
                    qualified_name=f"{config.name}_search",
                    description=f"{config.name} search",
                    input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
                )
            ],
        )

    manager = MCPClientManager(
        config_path=config_path,
        connector_factory=_connector,
    )
    manager.set_enabled(True)
    manager.set_server_enabled("notes", False)

    tools = await manager.get_tools()
    cached = manager.list_cached_tools()
    statuses = await manager.get_server_statuses()

    assert [tool.name for tool in tools] == ["weather_search"]
    assert [tool.name for tool in cached] == ["weather_search"]
    assert connect_calls == ["weather"]
    assert {status.name: status.enabled for status in statuses} == {
        "weather": True,
        "notes": False,
    }

    # cached second call should not reconnect
    again = await manager.get_tools()
    assert [tool.name for tool in again] == ["weather_search"]
    assert connect_calls == ["weather"]


@pytest.mark.anyio
async def test_client_manager_degrades_failed_servers_without_blocking_other_tools(tmp_path: Path):
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "broken": {"command": "python", "args": ["-m", "broken_server"]},
                    "weather": {"command": "python", "args": ["-m", "weather_server"]},
                }
            }
        ),
        encoding="utf-8",
    )

    async def _connector(config: MCPServerConfig):
        if config.name == "broken":
            raise RuntimeError("boom")
        return _FakeClient(
            config.name,
            [
                MCPToolInfo(
                    server_name=config.name,
                    name="forecast",
                    qualified_name=f"{config.name}_forecast",
                    description="forecast",
                    input_schema={"type": "object", "properties": {}},
                )
            ],
        )

    manager = MCPClientManager(
        config_path=config_path,
        connector_factory=_connector,
    )
    manager.set_enabled(True)

    tools = await manager.get_tools()
    statuses = {status.name: status for status in await manager.get_server_statuses()}

    assert [tool.name for tool in tools] == ["weather_forecast"]
    assert statuses["weather"].connection_status == "connected"
    assert statuses["broken"].connection_status == "error"
    assert statuses["broken"].error_message == "boom"


@pytest.mark.anyio
async def test_client_manager_normalizes_tool_name_as_server_tool(tmp_path: Path):
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "filesystem": {"command": "python", "args": ["-m", "filesystem_server"]},
                }
            }
        ),
        encoding="utf-8",
    )

    class _DictClient(_FakeClient):
        async def list_tools(self) -> list[dict]:
            return [
                {
                    "name": "read_file",
                    "description": "Read file contents",
                    "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}},
                }
            ]

    async def _connector(config: MCPServerConfig):
        return _DictClient(config.name, [])

    manager = MCPClientManager(config_path=config_path, connector_factory=_connector)
    manager.set_enabled(True)

    tools = await manager.get_tools()

    assert [tool.name for tool in tools] == ["filesystem_read_file"]


@pytest.mark.anyio
async def test_client_manager_normalizes_sdk_style_tool_objects(tmp_path: Path):
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "filesystem": {"command": "python", "args": ["-m", "filesystem_server"]},
                }
            }
        ),
        encoding="utf-8",
    )

    class _SdkTool:
        def __init__(self):
            self.name = "read_file"
            self.description = "Read file contents"
            self.inputSchema = {"type": "object", "properties": {"path": {"type": "string"}}}

    class _ObjectClient(_FakeClient):
        async def list_tools(self):
            return [_SdkTool()]

    async def _connector(config: MCPServerConfig):
        return _ObjectClient(config.name, [])

    manager = MCPClientManager(config_path=config_path, connector_factory=_connector)
    manager.set_enabled(True)

    tools = await manager.get_tools()

    assert [tool.name for tool in tools] == ["filesystem_read_file"]
