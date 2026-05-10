"""Path helpers for MCP configuration files."""

from __future__ import annotations

from pathlib import Path

from newbee_notebook.core.common.project_paths import get_configs_directory


def get_mcp_config_directory() -> Path:
    """Return the repository MCP configuration directory."""

    return get_configs_directory() / "mcp"


def get_mcp_config_path() -> Path:
    """Return the active MCP server definition path."""

    return get_mcp_config_directory() / "mcp.json"


def get_mcp_example_config_path() -> Path:
    """Return the MCP example configuration path."""

    return get_mcp_config_directory() / "mcp.example.json"
