from __future__ import annotations

import json
from pathlib import Path

import pytest

from newbee_notebook.core.mcp.client_manager import MCPClientManager


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_stdio_mcp_server_round_trip(tmp_path: Path):
    server_script = tmp_path / "demo_mcp_server.py"
    server_script.write_text(
        """
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("demo")

@mcp.tool(description="Echo the provided text")
def echo(text: str) -> str:
    return f"echo:{text}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
""".strip(),
        encoding="utf-8",
    )

    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "demo": {
                        "command": "D:/Projects/notebook-project/newbee-notebook/.venv/Scripts/python.exe",
                        "args": [str(server_script)],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    manager = MCPClientManager(config_path=config_path)
    manager.set_enabled(True)

    tools = await manager.get_tools()
    assert [tool.name for tool in tools] == ["demo_echo"]

    result = await tools[0].execute({"text": "hello"})
    assert result.content == "echo:hello"
    assert result.error is None

    statuses = await manager.get_server_statuses()
    assert statuses[0].connection_status == "connected"
    assert statuses[0].tool_count == 1

    await manager.shutdown()
