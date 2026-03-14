"""Core MCP data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    transport: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MCPServerStatus:
    name: str
    transport: str
    enabled: bool
    connection_status: str
    tool_count: int = 0
    error_message: str | None = None


@dataclass(frozen=True)
class MCPToolInfo:
    server_name: str
    name: str
    qualified_name: str
    description: str
    input_schema: dict[str, Any]


class MCPClientProtocol(Protocol):
    async def list_tools(self) -> list[MCPToolInfo | dict[str, Any]]:
        ...

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        ...

    async def close(self) -> None:
        ...
