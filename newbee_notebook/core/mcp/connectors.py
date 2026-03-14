"""Official MCP SDK transport connectors."""

from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any

from newbee_notebook.core.mcp.types import MCPClientProtocol, MCPServerConfig

try:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from mcp.client.streamable_http import streamablehttp_client
except ModuleNotFoundError:  # pragma: no cover
    ClientSession = None  # type: ignore[assignment]
    StdioServerParameters = None  # type: ignore[assignment]
    stdio_client = None  # type: ignore[assignment]
    streamablehttp_client = None  # type: ignore[assignment]


class SDKMCPClient(MCPClientProtocol):
    def __init__(self, *, session: Any, exit_stack: AsyncExitStack):
        self._session = session
        self._exit_stack = exit_stack

    async def list_tools(self) -> list[Any]:
        result = await self._session.list_tools()
        return list(getattr(result, "tools", []) or [])

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        return await self._session.call_tool(tool_name, arguments)

    async def close(self) -> None:
        await self._exit_stack.aclose()


def _require_sdk() -> None:
    if ClientSession is None or stdio_client is None or streamablehttp_client is None:
        raise RuntimeError("MCP SDK is not installed")


async def connect_mcp_server(config: MCPServerConfig) -> MCPClientProtocol:
    _require_sdk()
    if config.transport == "stdio":
        if not config.command:
            raise ValueError(f"stdio MCP server requires command: {config.name}")
        transport_context = stdio_client(
            StdioServerParameters(
                command=config.command,
                args=list(config.args),
                env=dict(config.env),
            )
        )
    elif config.transport == "streamable-http":
        if not config.url:
            raise ValueError(f"streamable-http MCP server requires url: {config.name}")
        transport_context = streamablehttp_client(
            config.url,
            headers=dict(config.headers) or None,
        )
    else:
        raise ValueError(f"Unsupported MCP transport: {config.transport}")

    exit_stack = AsyncExitStack()
    streams = await exit_stack.enter_async_context(transport_context)
    if len(streams) >= 2:
        read_stream, write_stream = streams[0], streams[1]
    else:  # pragma: no cover
        await exit_stack.aclose()
        raise RuntimeError("Invalid MCP transport stream tuple")

    session = await exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
    await session.initialize()
    return SDKMCPClient(session=session, exit_stack=exit_stack)
