from __future__ import annotations

import json
from pathlib import Path

import pytest

from newbee_notebook.api import dependencies
from newbee_notebook.core.mcp.config import load_mcp_config


def test_load_mcp_config_supports_stdio_and_streamable_http(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MCP_TOKEN", "secret-token")
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "filesystem": {
                        "command": "python",
                        "args": ["-m", "filesystem_server"],
                    },
                    "weather": {
                        "type": "streamable-http",
                        "url": "https://example.com/mcp",
                        "headers": {
                            "Authorization": "Bearer ${MCP_TOKEN}",
                            "X-Fallback": "${MISSING_HEADER:-fallback}",
                        },
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    configs = load_mcp_config(config_path)

    assert [(cfg.name, cfg.transport) for cfg in configs] == [
        ("filesystem", "stdio"),
        ("weather", "streamable-http"),
    ]
    assert configs[1].headers["Authorization"] == "Bearer secret-token"
    assert configs[1].headers["X-Fallback"] == "fallback"


def test_load_mcp_config_accepts_utf8_bom(tmp_path: Path):
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "demo": {
                        "command": "python",
                        "args": ["-m", "demo_server"],
                    }
                }
            }
        ),
        encoding="utf-8-sig",
    )

    configs = load_mcp_config(config_path)

    assert len(configs) == 1
    assert configs[0].name == "demo"
    assert configs[0].transport == "stdio"


def test_load_mcp_config_rejects_unsupported_transport(tmp_path: Path):
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "legacy": {
                        "type": "sse",
                        "url": "https://example.com/sse",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unsupported MCP transport"):
        load_mcp_config(config_path)


def test_runtime_mcp_singleton_uses_repo_level_configs_path(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(dependencies, "_mcp_client_manager", None)

    manager = dependencies.get_mcp_client_manager_singleton()

    try:
        assert manager._config_path.name == "mcp.json"
        assert manager._config_path.parent.name == "configs"
        assert manager._config_path.parent.parent.name == "batch-2-core"
    finally:
        monkeypatch.setattr(dependencies, "_mcp_client_manager", None)
