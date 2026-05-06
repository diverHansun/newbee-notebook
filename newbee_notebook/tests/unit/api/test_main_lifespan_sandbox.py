from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_lifespan_stops_runtime_docker_sessions_on_shutdown(monkeypatch):
    from newbee_notebook.api import main

    calls: list[str] = []

    async def fake_stop_runtime_docker_sessions():
        calls.append("stop")

    async def fake_stop_runtime_docker_session_reaper():
        calls.append("stop_reaper")

    monkeypatch.setattr(
        main,
        "stop_runtime_docker_sessions",
        fake_stop_runtime_docker_sessions,
    )
    monkeypatch.setattr(
        main,
        "stop_runtime_docker_session_reaper",
        fake_stop_runtime_docker_session_reaper,
    )
    monkeypatch.setattr(main, "start_runtime_docker_session_reaper", lambda: None)

    async with main.lifespan(main.create_app()):
        pass

    assert calls == ["stop_reaper", "stop"]
