from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from newbee_notebook.api.dependencies import get_session_service
from newbee_notebook.api.routers.sessions import router
from newbee_notebook.application.services.session_service import SessionLimitExceededError
from newbee_notebook.domain.entities.message import Message
from newbee_notebook.domain.value_objects.mode_type import MessageRole, MessageType, ModeType


class _FakeSessionService:
    async def create(self, notebook_id: str, title: str | None = None, include_ec_context: bool = False):
        del notebook_id, title, include_ec_context
        raise SessionLimitExceededError(50)

    async def list_messages(self, session_id: str, modes=None, limit: int = 50, offset: int = 0):
        del modes, limit, offset
        return (
            [
                Message(
                    message_id=11,
                    session_id=session_id,
                    mode=ModeType.AGENT,
                    role=MessageRole.ASSISTANT,
                    message_type=MessageType.SUMMARY,
                    content="Compacted summary",
                    created_at=datetime(2026, 3, 27, 12, 0, 0),
                ),
                Message(
                    message_id=12,
                    session_id=session_id,
                    mode=ModeType.AGENT,
                    role=MessageRole.USER,
                    message_type=MessageType.NORMAL,
                    content="Latest question",
                    created_at=datetime(2026, 3, 27, 12, 1, 0),
                ),
            ],
            2,
        )

    async def get_or_raise(self, session_id: str):
        return SimpleNamespace(session_id=session_id)


def test_list_session_messages_includes_message_type_and_summary_rows():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_session_service] = lambda: _FakeSessionService()
    client = TestClient(app)

    response = client.get("/api/v1/sessions/session-1/messages")

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 2
    assert body["data"][0]["message_type"] == "summary"
    assert body["data"][0]["content"] == "Compacted summary"
    assert body["data"][1]["message_type"] == "normal"


def test_create_session_returns_400_with_50_session_limit_contract():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_session_service] = lambda: _FakeSessionService()
    client = TestClient(app)

    response = client.post("/api/v1/notebooks/notebook-1/sessions", json={})

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error_code"] == "E3001"
    assert detail["details"]["current_count"] == 50
    assert detail["details"]["max_count"] == 50
