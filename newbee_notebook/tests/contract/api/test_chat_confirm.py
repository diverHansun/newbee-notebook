from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from newbee_notebook.api.dependencies import (
    get_chat_service,
    get_policy_preference_service,
    get_session_service,
)
from newbee_notebook.api.routers import chat as chat_router


class _FakeSession:
    session_id = "session-1"
    notebook_id = "nb-1"


class _FakeSessionService:
    async def get_or_raise(self, session_id: str):
        assert session_id == "session-1"
        return _FakeSession()


class _FakePolicyService:
    def __init__(self) -> None:
        self.session_updates: list[dict] = []
        self.notebook_updates: list[dict] = []

    async def update_session(self, **kwargs):
        self.session_updates.append(kwargs)
        return type(
            "_Policy",
            (),
            {
                "notebook_id": kwargs["notebook_id"],
                "session_id": kwargs["session_id"],
                "policy": kwargs["policy"],
                "source": "session",
            },
        )()

    async def update_notebook(self, **kwargs):
        self.notebook_updates.append(kwargs)
        return type(
            "_Policy",
            (),
            {
                "notebook_id": kwargs["notebook_id"],
                "session_id": kwargs["session_id"],
                "policy": kwargs["policy"],
                "source": "notebook",
            },
        )()


def _build_client(
    chat_service: AsyncMock,
    policy_service: _FakePolicyService | None = None,
) -> TestClient:
    app = FastAPI()
    app.include_router(chat_router.router, prefix="/api/v1")
    policy_service = policy_service or _FakePolicyService()

    async def _override_chat():
        return chat_service

    async def _override_session():
        return _FakeSessionService()

    app.dependency_overrides[get_chat_service] = _override_chat
    app.dependency_overrides[get_session_service] = _override_session
    app.dependency_overrides[get_policy_preference_service] = lambda: policy_service
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


def test_permission_resolve_endpoint_accepts_response_choice():
    chat_service = AsyncMock()
    chat_service.resolve_permission_request = AsyncMock(return_value=True)
    policy_service = _FakePolicyService()
    client = _build_client(chat_service, policy_service)

    response = client.post(
        "/api/v1/chat/session-1/permission-requests/resolve",
        json={"request_id": "req-1", "response": "always_session"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "resolved"
    chat_service.resolve_permission_request.assert_awaited_once_with(
        session_id="session-1",
        request_id="req-1",
        approved=None,
        response="always_session",
        suggestion=None,
    )


def test_permission_resolve_endpoint_uses_permission_response_schema():
    chat_service = AsyncMock()
    client = _build_client(chat_service)

    response = client.get("/openapi.json")

    schema_ref = response.json()["paths"][
        "/api/v1/chat/{session_id}/permission-requests/resolve"
    ]["post"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    assert schema_ref.endswith("/PermissionResolveResponse")


def test_confirm_endpoint_accepts_permission_response_choice():
    chat_service = AsyncMock()
    chat_service.confirm_action = AsyncMock(return_value=True)
    policy_service = _FakePolicyService()
    client = _build_client(chat_service, policy_service)

    response = client.post(
        "/api/v1/chat/session-1/confirm",
        json={
            "request_id": "req-1",
            "response": "always_persist",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "resolved",
        "effective_policy": {
            "notebook_id": "nb-1",
            "session_id": "session-1",
            "policy": "yolo",
            "source": "notebook",
        },
    }
    chat_service.confirm_action.assert_awaited_once_with(
        session_id="session-1",
        request_id="req-1",
        approved=None,
        response="always_persist",
        suggestion=None,
    )
    assert policy_service.notebook_updates == [
        {"notebook_id": "nb-1", "session_id": "session-1", "policy": "yolo"}
    ]


def test_confirm_endpoint_updates_session_policy_for_always_session():
    chat_service = AsyncMock()
    chat_service.confirm_action = AsyncMock(return_value=True)
    policy_service = _FakePolicyService()
    client = _build_client(chat_service, policy_service)

    response = client.post(
        "/api/v1/chat/session-1/confirm",
        json={
            "request_id": "req-1",
            "response": "always_session",
        },
    )

    assert response.status_code == 200
    assert response.json()["effective_policy"] == {
        "notebook_id": "nb-1",
        "session_id": "session-1",
        "policy": "yolo",
        "source": "session",
    }
    assert policy_service.session_updates == [
        {"notebook_id": "nb-1", "session_id": "session-1", "policy": "yolo"}
    ]


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
