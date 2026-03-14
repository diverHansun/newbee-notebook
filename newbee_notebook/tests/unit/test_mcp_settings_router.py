from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from newbee_notebook.api.dependencies import get_app_settings_service, get_mcp_client_manager_dep
from newbee_notebook.api.routers import settings as settings_router


class _FakeSettingsService:
    def __init__(self, store: dict[str, str]):
        self._store = store

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: str):
        self._store[key] = value


class _FakeMCPManager:
    def __init__(self):
        self.enabled = True
        self.server_enabled: dict[str, bool] = {}
        self.disabled_servers: list[str] = []
        self.enabled_servers: list[str] = []
        self.shutdown_calls = 0
        self.statuses = [
            {
                "name": "filesystem",
                "transport": "stdio",
                "enabled": True,
                "connection_status": "connected",
                "tool_count": 2,
                "error_message": None,
            },
            {
                "name": "weather",
                "transport": "streamable-http",
                "enabled": False,
                "connection_status": "disconnected",
                "tool_count": 0,
                "error_message": None,
            },
        ]

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def set_server_enabled(self, name: str, enabled: bool) -> None:
        self.server_enabled[name] = enabled

    async def get_server_statuses(self):
        return self.statuses

    async def enable_server(self, name: str):
        self.enabled_servers.append(name)

    async def disable_server(self, name: str):
        self.disabled_servers.append(name)

    async def shutdown(self):
        self.shutdown_calls += 1


def _build_client():
    app = FastAPI()
    app.include_router(settings_router.router, prefix="/api/v1")

    store = {
        "mcp.enabled": "true",
        "mcp.servers.filesystem.enabled": "true",
        "mcp.servers.weather.enabled": "false",
    }
    manager = _FakeMCPManager()

    async def _settings_dep():
        return _FakeSettingsService(store)

    async def _mcp_dep():
        return manager

    app.dependency_overrides[get_app_settings_service] = _settings_dep
    app.dependency_overrides[get_mcp_client_manager_dep] = _mcp_dep
    return TestClient(app), store, manager


def test_get_mcp_servers_status_returns_effective_switches():
    client, _store, _manager = _build_client()

    response = client.get("/api/v1/settings/mcp/servers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mcp_enabled"] is True
    assert [server["name"] for server in payload["servers"]] == ["filesystem", "weather"]
    assert payload["servers"][0]["transport"] == "stdio"
    assert payload["servers"][1]["transport"] == "streamable-http"


def test_put_settings_disables_single_server_immediately():
    client, store, manager = _build_client()

    response = client.put(
        "/api/v1/settings",
        json={"key": "mcp.servers.filesystem.enabled", "value": "false"},
    )

    assert response.status_code == 200
    assert store["mcp.servers.filesystem.enabled"] == "false"
    assert manager.disabled_servers == ["filesystem"]


def test_put_settings_disables_total_mcp_immediately():
    client, store, manager = _build_client()

    response = client.put(
        "/api/v1/settings",
        json={"key": "mcp.enabled", "value": "false"},
    )

    assert response.status_code == 200
    assert store["mcp.enabled"] == "false"
    assert manager.enabled is False
    assert manager.shutdown_calls == 1
