"""Cached MCP client manager for agent-mode tool injection."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

from newbee_notebook.core.mcp.config import load_mcp_config
from newbee_notebook.core.mcp.tool_adapter import MCPToolAdapter
from newbee_notebook.core.mcp.types import (
    MCPClientProtocol,
    MCPServerConfig,
    MCPServerStatus,
    MCPToolInfo,
)
from newbee_notebook.core.tools.contracts import ToolDefinition

logger = logging.getLogger(__name__)

MCPConnectorFactory = Callable[[MCPServerConfig], Awaitable[MCPClientProtocol]]


async def _missing_connector_factory(_: MCPServerConfig) -> MCPClientProtocol:
    raise RuntimeError("MCP SDK is not installed")


class MCPClientManager:
    def __init__(
        self,
        *,
        config_path: Path,
        connector_factory: MCPConnectorFactory | None = None,
        config_loader: Callable[[Path], list[MCPServerConfig]] = load_mcp_config,
    ):
        self._config_path = config_path
        self._connector_factory = connector_factory or _missing_connector_factory
        self._config_loader = config_loader
        self._enabled = False
        self._server_enabled: dict[str, bool] = {}
        self._configs: dict[str, MCPServerConfig] = {}
        self._config_order: list[str] = []
        self._clients: dict[str, MCPClientProtocol] = {}
        self._tool_infos: dict[str, list[MCPToolInfo]] = {}
        self._statuses: dict[str, MCPServerStatus] = {}

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)

    def set_server_enabled(self, name: str, enabled: bool) -> None:
        self._server_enabled[str(name)] = bool(enabled)

    def list_cached_tools(self) -> list[ToolDefinition]:
        tools: list[ToolDefinition] = []
        for server_name in self._config_order:
            for tool_info in self._tool_infos.get(server_name, []):
                tools.append(
                    MCPToolAdapter.adapt(
                        tool_info,
                        invoke_tool=lambda tool_name, arguments, server_name=server_name: self._call_tool(
                            server_name, tool_name, arguments
                        ),
                    )
                )
        return tools

    async def get_tools(self) -> list[ToolDefinition]:
        self._load_configs()
        await self._disconnect_removed_servers(set(self._configs))
        for server_name in self._config_order:
            config = self._configs[server_name]
            if not self._enabled or not self._is_server_enabled(server_name):
                await self._disconnect_server(server_name, enabled=False)
                continue
            if server_name in self._clients and server_name in self._tool_infos:
                self._statuses[server_name] = MCPServerStatus(
                    name=server_name,
                    transport=config.transport,
                    enabled=True,
                    connection_status="connected",
                    tool_count=len(self._tool_infos[server_name]),
                )
                continue
            await self._connect_server(config)
        return self.list_cached_tools()

    async def get_server_statuses(self) -> list[MCPServerStatus]:
        self._load_configs()
        statuses: list[MCPServerStatus] = []
        for server_name in self._config_order:
            config = self._configs[server_name]
            if server_name not in self._statuses:
                self._statuses[server_name] = MCPServerStatus(
                    name=server_name,
                    transport=config.transport,
                    enabled=self._enabled and self._is_server_enabled(server_name),
                    connection_status="disconnected",
                )
            statuses.append(self._statuses[server_name])
        return statuses

    async def enable_server(self, name: str) -> None:
        self.set_server_enabled(name, True)
        self._load_configs()
        config = self._configs.get(name)
        if config and self._enabled:
            await self._connect_server(config)

    async def disable_server(self, name: str) -> None:
        self.set_server_enabled(name, False)
        await self._disconnect_server(name, enabled=False)

    async def shutdown(self) -> None:
        for server_name in list(self._clients):
            await self._disconnect_server(server_name, enabled=self._enabled and self._is_server_enabled(server_name))
        self._clients.clear()
        self._tool_infos.clear()

    def _load_configs(self) -> None:
        configs = self._config_loader(self._config_path)
        self._configs = {config.name: config for config in configs}
        self._config_order = [config.name for config in configs]

    def _is_server_enabled(self, name: str) -> bool:
        return self._server_enabled.get(name, True)

    async def _disconnect_removed_servers(self, active_names: set[str]) -> None:
        for server_name in list(self._clients):
            if server_name not in active_names:
                await self._disconnect_server(server_name, enabled=False)
                self._statuses.pop(server_name, None)

    async def _connect_server(self, config: MCPServerConfig) -> None:
        self._statuses[config.name] = MCPServerStatus(
            name=config.name,
            transport=config.transport,
            enabled=True,
            connection_status="connecting",
        )
        try:
            client = await self._connector_factory(config)
            raw_tools = await client.list_tools()
            tool_infos = [self._normalize_tool_info(config.name, raw_tool) for raw_tool in raw_tools]
            self._clients[config.name] = client
            self._tool_infos[config.name] = tool_infos
            self._statuses[config.name] = MCPServerStatus(
                name=config.name,
                transport=config.transport,
                enabled=True,
                connection_status="connected",
                tool_count=len(tool_infos),
            )
        except Exception as exc:
            logger.warning("Failed connecting MCP server %s: %s", config.name, exc)
            self._clients.pop(config.name, None)
            self._tool_infos.pop(config.name, None)
            self._statuses[config.name] = MCPServerStatus(
                name=config.name,
                transport=config.transport,
                enabled=True,
                connection_status="error",
                error_message=str(exc),
            )

    async def _disconnect_server(self, server_name: str, *, enabled: bool) -> None:
        client = self._clients.pop(server_name, None)
        self._tool_infos.pop(server_name, None)
        if client is not None:
            try:
                await client.close()
            except Exception:
                logger.debug("Failed closing MCP client for %s", server_name, exc_info=True)

        config = self._configs.get(server_name)
        if config is not None:
            self._statuses[server_name] = MCPServerStatus(
                name=server_name,
                transport=config.transport,
                enabled=enabled,
                connection_status="disconnected",
            )

    def _normalize_tool_info(self, server_name: str, raw_tool: MCPToolInfo | dict[str, Any]) -> MCPToolInfo:
        if isinstance(raw_tool, MCPToolInfo):
            if raw_tool.qualified_name:
                return raw_tool
            return MCPToolInfo(
                server_name=server_name,
                name=raw_tool.name,
                qualified_name=f"{server_name}__{raw_tool.name}",
                description=raw_tool.description,
                input_schema=raw_tool.input_schema,
            )

        name = str(raw_tool.get("name") or "")
        description = str(raw_tool.get("description") or "")
        schema = dict(raw_tool.get("input_schema") or raw_tool.get("inputSchema") or {"type": "object", "properties": {}})
        return MCPToolInfo(
            server_name=server_name,
            name=name,
            qualified_name=f"{server_name}__{name}",
            description=description,
            input_schema=schema,
        )

    async def _call_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> Any:
        client = self._clients.get(server_name)
        if client is None:
            raise RuntimeError(f"MCP server is not connected: {server_name}")
        return await client.call_tool(tool_name, arguments)
