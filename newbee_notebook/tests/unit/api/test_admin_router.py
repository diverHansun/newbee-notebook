import asyncio

import requests

from newbee_notebook.api.routers import admin


def test_system_memory_probes_mineru_health_endpoint(monkeypatch):
    calls: list[str] = []

    class _Response:
        ok = True
        status_code = 200

    monkeypatch.setattr(admin, "_get_mineru_probe_urls", lambda: ["http://mineru-api:8000"])
    monkeypatch.setattr(admin.http_requests, "get", lambda url, timeout: calls.append(url) or _Response())

    result = asyncio.run(admin.system_memory())

    assert calls == ["http://mineru-api:8000/health"]
    assert result.mineru["status"] == "healthy"
    assert result.mineru["probe_url"] == "http://mineru-api:8000"


def test_system_memory_uses_fallback_probe_after_connection_error(monkeypatch):
    calls: list[str] = []

    class _Response:
        ok = True
        status_code = 200

    def _fake_get(url, timeout):  # noqa: ANN001
        calls.append(url)
        if url.startswith("http://mineru-api:8000"):
            raise requests.ConnectionError("primary unreachable")
        return _Response()

    monkeypatch.setattr(
        admin,
        "_get_mineru_probe_urls",
        lambda: ["http://mineru-api:8000", "http://localhost:8001"],
    )
    monkeypatch.setattr(admin.http_requests, "get", _fake_get)

    result = asyncio.run(admin.system_memory())

    assert calls == [
        "http://mineru-api:8000/health",
        "http://localhost:8001/health",
    ]
    assert result.mineru["status"] == "healthy"
    assert result.mineru["probe_url"] == "http://localhost:8001"
    assert "fallback probe url" in result.mineru["note"]

