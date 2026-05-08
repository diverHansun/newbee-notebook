from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from newbee_notebook.api.dependencies import (
    get_app_settings_service,
    get_notebook_service,
    get_permission_session_cache_dep,
    get_session_service,
)
from newbee_notebook.api.routers import policy as policy_router
from newbee_notebook.application.services.notebook_service import NotebookNotFoundError
from newbee_notebook.core.permission import SessionAllowCache


class FakeSettings:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def get_many(self, prefix: str) -> dict[str, str]:
        return {
            key: value
            for key, value in self.values.items()
            if key.startswith(prefix)
        }

    async def set(self, key: str, value: str) -> None:
        self.values[key] = value

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)


class FakeSession:
    def __init__(self, session_id: str = "session-1", notebook_id: str = "nb-1") -> None:
        self.session_id = session_id
        self.notebook_id = notebook_id


class FakeSessionService:
    async def get_or_raise(self, session_id: str):
        if session_id != "session-1":
            raise ValueError("Session not found")
        return FakeSession()

    async def list_by_notebook(self, notebook_id: str, limit: int = 20, offset: int = 0):
        del limit, offset
        return [FakeSession("session-1", notebook_id), FakeSession("session-2", notebook_id)], 2


class FakeNotebookService:
    async def get_or_raise(self, notebook_id: str):
        if notebook_id != "nb-1":
            raise NotebookNotFoundError(f"Notebook not found: {notebook_id}")
        return object()


def _build_client() -> tuple[TestClient, FakeSettings]:
    settings = FakeSettings()
    cache = SessionAllowCache()
    app = FastAPI()
    app.include_router(policy_router.router, prefix="/api/v1")
    app.dependency_overrides[get_app_settings_service] = lambda: settings
    app.dependency_overrides[get_notebook_service] = lambda: FakeNotebookService()
    app.dependency_overrides[get_session_service] = lambda: FakeSessionService()
    app.dependency_overrides[get_permission_session_cache_dep] = lambda: cache
    return TestClient(app), settings


def test_policy_effective_defaults_to_default():
    client, _settings = _build_client()

    response = client.get(
        "/api/v1/policy/notebooks/nb-1/effective?session_id=session-1"
    )

    assert response.status_code == 200
    assert response.json() == {
        "notebook_id": "nb-1",
        "session_id": "session-1",
        "policy": "default",
        "source": "default",
    }


def test_policy_update_session_scope():
    client, settings = _build_client()

    response = client.put(
        "/api/v1/policy/notebooks/nb-1",
        json={"scope": "session", "session_id": "session-1", "policy": "yolo"},
    )

    assert response.status_code == 200
    assert response.json()["policy"] == "yolo"
    assert response.json()["source"] == "session"
    assert settings.values["policy.sessions.session-1.agent_policy"] == "yolo"


def test_policy_update_notebook_scope():
    client, settings = _build_client()

    response = client.put(
        "/api/v1/policy/notebooks/nb-1",
        json={"scope": "notebook", "policy": "yolo"},
    )

    assert response.status_code == 200
    assert response.json()["policy"] == "yolo"
    assert response.json()["source"] == "notebook"
    assert settings.values["policy.notebooks.nb-1.agent_policy"] == "yolo"


def test_policy_default_clears_visible_session_scope():
    client, settings = _build_client()
    settings.values["policy.sessions.session-1.agent_policy"] = "yolo"

    response = client.put(
        "/api/v1/policy/notebooks/nb-1",
        json={"scope": "session", "session_id": "session-1", "policy": "default"},
    )

    assert response.status_code == 200
    assert response.json()["policy"] == "default"
    assert response.json()["source"] == "default"
    assert "policy.sessions.session-1.agent_policy" not in settings.values


def test_policy_default_clears_current_session_allow_all_cache():
    settings = FakeSettings()
    cache = SessionAllowCache()
    cache.add_all("session-1")
    app = FastAPI()
    app.include_router(policy_router.router, prefix="/api/v1")
    app.dependency_overrides[get_app_settings_service] = lambda: settings
    app.dependency_overrides[get_notebook_service] = lambda: FakeNotebookService()
    app.dependency_overrides[get_session_service] = lambda: FakeSessionService()
    app.dependency_overrides[get_permission_session_cache_dep] = lambda: cache
    client = TestClient(app)

    response = client.put(
        "/api/v1/policy/notebooks/nb-1",
        json={"scope": "session", "session_id": "session-1", "policy": "default"},
    )

    assert response.status_code == 200
    assert not cache.contains("session-1", "global:bash:abc")


def test_policy_notebook_default_clears_allow_all_cache_for_notebook_sessions():
    settings = FakeSettings()
    settings.values["policy.notebooks.nb-1.agent_policy"] = "yolo"
    cache = SessionAllowCache()
    cache.add_all("session-1")
    cache.add_all("session-2")
    app = FastAPI()
    app.include_router(policy_router.router, prefix="/api/v1")
    app.dependency_overrides[get_app_settings_service] = lambda: settings
    app.dependency_overrides[get_notebook_service] = lambda: FakeNotebookService()
    app.dependency_overrides[get_session_service] = lambda: FakeSessionService()
    app.dependency_overrides[get_permission_session_cache_dep] = lambda: cache
    client = TestClient(app)

    response = client.put(
        "/api/v1/policy/notebooks/nb-1",
        json={"scope": "notebook", "policy": "default"},
    )

    assert response.status_code == 200
    assert not cache.contains("session-1", "global:bash:abc")
    assert not cache.contains("session-2", "global:write_file:def")


def test_policy_update_unknown_notebook_returns_404():
    client, settings = _build_client()

    response = client.put(
        "/api/v1/policy/notebooks/missing",
        json={"scope": "notebook", "policy": "yolo"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Notebook not found"
    assert settings.values == {}
