from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from newbee_notebook.api.dependencies import get_chat_service, get_session_service
from newbee_notebook.api.routers import chat as chat_router


def _build_client(chat_service: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(chat_router.router, prefix="/api/v1")

    async def _override_chat():
        return chat_service

    async def _override_session():
        return AsyncMock()

    app.dependency_overrides[get_chat_service] = _override_chat
    app.dependency_overrides[get_session_service] = _override_session
    return TestClient(app)


def test_confirm_endpoint_accepts_legacy_boolean_approval():
    chat_service = AsyncMock()
    chat_service.confirm_action = AsyncMock(return_value=True)
    client = _build_client(chat_service)

    response = client.post(
        "/api/v1/chat/session-1/confirm",
        json={"request_id": "req-1", "approved": True},
    )

    assert response.status_code == 200
    chat_service.confirm_action.assert_awaited_once_with(
        session_id="session-1",
        request_id="req-1",
        approved=True,
        response=None,
        suggestion=None,
    )


def test_confirm_endpoint_accepts_permission_response_choice():
    chat_service = AsyncMock()
    chat_service.confirm_action = AsyncMock(return_value=True)
    client = _build_client(chat_service)

    response = client.post(
        "/api/v1/chat/session-1/confirm",
        json={
            "request_id": "req-1",
            "response": "always_persist",
        },
    )

    assert response.status_code == 200
    chat_service.confirm_action.assert_awaited_once_with(
        session_id="session-1",
        request_id="req-1",
        approved=None,
        response="always_persist",
        suggestion=None,
    )


def test_confirm_endpoint_accepts_reject_suggestion():
    chat_service = AsyncMock()
    chat_service.confirm_action = AsyncMock(return_value=True)
    client = _build_client(chat_service)

    response = client.post(
        "/api/v1/chat/session-1/confirm",
        json={
            "request_id": "req-1",
            "response": "reject",
            "suggestion": "Please write to a temporary file instead.",
        },
    )

    assert response.status_code == 200
    chat_service.confirm_action.assert_awaited_once_with(
        session_id="session-1",
        request_id="req-1",
        approved=None,
        response="reject",
        suggestion="Please write to a temporary file instead.",
    )
