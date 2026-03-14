"""MCP config parsing."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from newbee_notebook.core.mcp.types import MCPServerConfig


_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]+))?\}")


def _expand_env(value: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        default = match.group(2)
        resolved = os.getenv(key)
        if resolved is None:
            if default is not None:
                return default
            raise ValueError(f"Missing required MCP environment variable: {key}")
        return resolved

    return _ENV_PATTERN.sub(_replace, value)


def _expand_value(value: Any) -> Any:
    if isinstance(value, str):
        return _expand_env(value)
    if isinstance(value, list):
        return [_expand_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _expand_value(item) for key, item in value.items()}
    return value


def load_mcp_config(config_path: Path) -> list[MCPServerConfig]:
    if not config_path.exists():
        return []

    payload = json.loads(config_path.read_text(encoding="utf-8-sig"))
    servers = payload.get("mcpServers") or {}
    configs: list[MCPServerConfig] = []

    for name, raw_server in servers.items():
        server = _expand_value(dict(raw_server or {}))
        transport = str(server.get("type") or ("stdio" if server.get("command") else "")).strip().lower()
        if transport in {"http", "streamable_http"}:
            transport = "streamable-http"
        if transport not in {"stdio", "streamable-http"}:
            raise ValueError(f"Unsupported MCP transport for {name}: {transport or '<missing>'}")

        configs.append(
            MCPServerConfig(
                name=str(name),
                transport=transport,
                command=server.get("command"),
                args=[str(item) for item in server.get("args", [])],
                env={str(key): str(value) for key, value in dict(server.get("env") or {}).items()},
                url=server.get("url"),
                headers={str(key): str(value) for key, value in dict(server.get("headers") or {}).items()},
            )
        )

    return configs
