from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from newbee_notebook.api.dependencies import get_bilibili_auth_manager
from newbee_notebook.api.routers import bilibili_auth as bilibili_auth_router


class _FakeAuthManager:
    def __init__(self, *, credential: dict | None = None):
        self._credential = credential
        self.clear_calls = 0

    def load_credential(self):
        return self._credential

    def clear_credential(self):
        self.clear_calls += 1
        self._credential = None

    async def stream_qr_login(self):
        yield ("qr_generated", {"qr_url": "https://example.com/qr"})
        yield ("done", {})


def _build_client(manager: _FakeAuthManager) -> TestClient:
    app = FastAPI()
    app.include_router(bilibili_auth_router.router, prefix="/api/v1")

    def _override():
        return manager

    app.dependency_overrides[get_bilibili_auth_manager] = _override
    return TestClient(app)


def test_auth_status_reflects_saved_credential():
    client = _build_client(_FakeAuthManager(credential={"sessdata": "abc"}))

    response = client.get("/api/v1/bilibili/auth/status")

    assert response.status_code == 200
    assert response.json() == {"logged_in": True}


def test_qr_login_route_streams_sse_events():
    client = _build_client(_FakeAuthManager())

    response = client.get("/api/v1/bilibili/auth/qr")

    assert response.status_code == 200
    assert "event: qr_generated" in response.text
    assert "event: done" in response.text


def test_logout_clears_credential():
    manager = _FakeAuthManager(credential={"sessdata": "abc"})
    client = _build_client(manager)

    response = client.post("/api/v1/bilibili/auth/logout")

    assert response.status_code == 204
    assert manager.clear_calls == 1
