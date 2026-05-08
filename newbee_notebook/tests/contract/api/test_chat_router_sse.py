import asyncio
import json
from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from newbee_notebook.api.dependencies import (
    get_chat_service,
    get_policy_preference_service,
    get_session_service,
)
from newbee_notebook.api.routers import chat as chat_router
from newbee_notebook.api.routers.chat import SSEEvent, heartbeat_generator
from newbee_notebook.application.services.session_service import SessionLimitExceededError
from newbee_notebook.exceptions import DocumentProcessingError


def test_sse_event_thinking_formats_stage():
    assert SSEEvent.thinking("searching") == 'data: {"type": "thinking", "stage": "searching"}\n\n'


def test_sse_event_phase_formats_stage():
    assert SSEEvent.format("phase", {"stage": "reasoning"}) == 'data: {"type": "phase", "stage": "reasoning"}\n\n'


def test_sse_event_warning_formats_payload():
    assert SSEEvent.warning(
        "partial_documents",
        "1 document is still processing; the current retrieval scope excludes it.",
        {"blocking_document_ids": ["doc-2"]},
    ) == (
        'data: {"type": "warning", "code": "partial_documents", '
        '"message": "1 document is still processing; the current retrieval scope excludes it.", '
        '"details": {"blocking_document_ids": ["doc-2"]}}\n\n'
    )


def test_sse_event_confirmation_request_formats_payload():
    assert SSEEvent.format(
        "confirmation_request",
        {
            "request_id": "req-1",
            "tool_name": "delete_note",
            "args_summary": {"note_id": "n1"},
            "description": "Agent requested to run delete_note",
        },
    ) == (
        'data: {"type": "confirmation_request", "request_id": "req-1", '
        '"tool_name": "delete_note", "args_summary": {"note_id": "n1"}, '
        '"description": "Agent requested to run delete_note"}\n\n'
    )


class _EffectivePolicy:
    def __init__(self, policy: str = "default", source: str = "default") -> None:
        self.notebook_id = "notebook-1"
        self.session_id = "session-1"
        self.policy = policy
        self.source = source


class _FakeSession:
    def __init__(self, session_id: str = "session-1", notebook_id: str = "notebook-1") -> None:
        self.session_id = session_id
        self.notebook_id = notebook_id


class _PolicyService:
    def __init__(self, policy: str = "default", source: str = "default") -> None:
        self.calls: list[dict[str, str | None]] = []
        self.policy = policy
        self.source = source

    async def get_effective(self, *, notebook_id: str, session_id: str | None = None):
        self.calls.append({"notebook_id": notebook_id, "session_id": session_id})
        return _EffectivePolicy(self.policy, self.source)


def _build_client(
    chat_service: AsyncMock,
    session_service: AsyncMock,
    policy_service: _PolicyService | None = None,
) -> TestClient:
    app = FastAPI()
    app.include_router(chat_router.router, prefix="/api/v1")
    policy_service = policy_service or _PolicyService()

    async def _override_chat():
        return chat_service

    async def _override_session():
        return session_service

    app.dependency_overrides[get_chat_service] = _override_chat
    app.dependency_overrides[get_session_service] = _override_session
    app.dependency_overrides[get_policy_preference_service] = lambda: policy_service
    return TestClient(app)


def test_chat_endpoint_returns_409_for_document_processing_error():
    chat_service = AsyncMock()
    chat_service.chat = AsyncMock(
        side_effect=DocumentProcessingError(
            "All documents are still processing; no searchable data is available yet."
        )
    )
    session_service = AsyncMock()
    session_service.get_or_raise = AsyncMock(return_value=_FakeSession())

    client = _build_client(chat_service, session_service)
    response = client.post(
        "/api/v1/chat/notebooks/notebook-1/chat",
        json={"session_id": "session-1", "message": "hi", "mode": "ask"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "All documents are still processing; no searchable data is available yet."
    )


def test_chat_stream_endpoint_returns_409_for_document_processing_error():
    chat_service = AsyncMock()
    chat_service.prevalidate_mode_requirements = AsyncMock(
        side_effect=DocumentProcessingError(
            "This document index is not ready yet, so explain/conclude is unavailable."
        )
    )
    session_service = AsyncMock()
    session_service.get_or_raise = AsyncMock(return_value=_FakeSession())

    client = _build_client(chat_service, session_service)
    response = client.post(
        "/api/v1/chat/notebooks/notebook-1/chat/stream",
        json={
            "session_id": "session-1",
            "message": "hi",
            "mode": "explain",
            "context": {"selected_text": "focus", "document_id": "doc-2"},
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "This document index is not ready yet, so explain/conclude is unavailable."
    )


def test_chat_endpoint_returns_400_for_session_limit_exceeded():
    chat_service = AsyncMock()
    session_service = AsyncMock()
    session_service.create = AsyncMock(side_effect=SessionLimitExceededError(50))

    client = _build_client(chat_service, session_service)
    response = client.post(
        "/api/v1/chat/notebooks/notebook-1/chat",
        json={"message": "hi", "mode": "agent"},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error_code"] == "E3001"
    assert detail["details"]["current_count"] == 50
    assert detail["details"]["max_count"] == 50


def test_chat_stream_endpoint_returns_400_for_session_limit_exceeded():
    chat_service = AsyncMock()
    session_service = AsyncMock()
    session_service.create = AsyncMock(side_effect=SessionLimitExceededError(50))

    client = _build_client(chat_service, session_service)
    response = client.post(
        "/api/v1/chat/notebooks/notebook-1/chat/stream",
        json={"message": "hi", "mode": "agent"},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error_code"] == "E3001"
    assert detail["details"]["current_count"] == 50
    assert detail["details"]["max_count"] == 50


def test_chat_endpoint_accepts_agent_mode():
    chat_service = AsyncMock()
    chat_service.chat = AsyncMock(
        return_value=type(
            "_Result",
            (),
            {
                "session_id": "session-1",
                "message_id": 1,
                "content": "hello",
                "mode": type("_Mode", (), {"value": "agent"})(),
                "sources": [],
                "warnings": [],
            },
        )()
    )
    session_service = AsyncMock()
    session_service.get_or_raise = AsyncMock(return_value=_FakeSession())

    client = _build_client(chat_service, session_service)
    response = client.post(
        "/api/v1/chat/notebooks/notebook-1/chat",
        json={"session_id": "session-1", "message": "hi", "mode": "agent"},
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "agent"


def test_chat_request_accepts_uploaded_image_ids():
    request = chat_router.ChatRequest(
        session_id="session-1",
        message="Please describe this image.",
        mode="agent",
        image_ids=["img-1"],
    )

    assert request.image_ids == ["img-1"]


def test_chat_request_rejects_image_only_payload_without_text():
    chat_service = AsyncMock()
    session_service = AsyncMock()
    session_service.get_or_raise = AsyncMock(return_value=_FakeSession())

    client = _build_client(chat_service, session_service)
    response = client.post(
        "/api/v1/chat/notebooks/notebook-1/chat",
        json={
            "session_id": "session-1",
            "message": "   ",
            "mode": "agent",
            "image_ids": ["img-1"],
        },
    )

    assert response.status_code == 422
    chat_service.chat.assert_not_awaited()


def test_chat_endpoint_passes_uploaded_image_ids_to_service():
    chat_service = AsyncMock()
    chat_service.chat = AsyncMock(
        return_value=type(
            "_Result",
            (),
            {
                "session_id": "session-1",
                "message_id": 1,
                "content": "hello",
                "mode": type("_Mode", (), {"value": "agent"})(),
                "sources": [],
                "warnings": [],
            },
        )()
    )
    session_service = AsyncMock()
    session_service.get_or_raise = AsyncMock(return_value=_FakeSession())

    client = _build_client(chat_service, session_service)
    response = client.post(
        "/api/v1/chat/notebooks/notebook-1/chat",
        json={
            "session_id": "session-1",
            "message": "Please describe this image.",
            "mode": "agent",
            "image_ids": ["img-1"],
        },
    )

    assert response.status_code == 200
    assert chat_service.chat.await_args.kwargs["image_ids"] == ["img-1"]


def test_chat_endpoint_uses_server_effective_policy_not_request_policy():
    chat_service = AsyncMock()
    chat_service.chat = AsyncMock(
        return_value=type(
            "_Result",
            (),
            {
                "session_id": "session-1",
                "message_id": 1,
                "content": "hello",
                "mode": type("_Mode", (), {"value": "agent"})(),
                "sources": [],
                "images": [],
                "warnings": [],
            },
        )()
    )
    session_service = AsyncMock()
    session_service.get_or_raise = AsyncMock(return_value=_FakeSession())
    policy_service = _PolicyService(policy="default")

    client = _build_client(chat_service, session_service, policy_service)
    response = client.post(
        "/api/v1/chat/notebooks/notebook-1/chat",
        json={
            "session_id": "session-1",
            "message": "hi",
            "mode": "agent",
            "agent_policy": "yolo",
        },
    )

    assert response.status_code == 200
    assert chat_service.chat.await_args.kwargs["agent_policy"] == "default"
    assert policy_service.calls == [
        {"notebook_id": "notebook-1", "session_id": "session-1"}
    ]


def test_chat_endpoint_rejects_session_from_another_notebook():
    chat_service = AsyncMock()
    chat_service.chat = AsyncMock()
    session_service = AsyncMock()
    session_service.get_or_raise = AsyncMock(
        return_value=_FakeSession(session_id="session-1", notebook_id="other-notebook")
    )
    policy_service = _PolicyService(policy="yolo", source="notebook")

    client = _build_client(chat_service, session_service, policy_service)
    response = client.post(
        "/api/v1/chat/notebooks/notebook-1/chat",
        json={"session_id": "session-1", "message": "hi", "mode": "agent"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Session does not belong to notebook"
    chat_service.chat.assert_not_awaited()
    assert policy_service.calls == []


def test_chat_stream_endpoint_passes_uploaded_image_ids_to_service():
    async def _stream():
        yield {"type": "start", "message_id": 1}
        yield {"type": "done"}

    chat_service = AsyncMock()
    chat_service.prevalidate_mode_requirements = AsyncMock(return_value=None)
    chat_service.chat_stream = Mock(return_value=_stream())
    session_service = AsyncMock()
    session_service.get_or_raise = AsyncMock(return_value=_FakeSession())

    policy_service = _PolicyService(policy="yolo", source="notebook")

    client = _build_client(chat_service, session_service, policy_service)
    response = client.post(
        "/api/v1/chat/notebooks/notebook-1/chat/stream",
        json={
            "session_id": "session-1",
            "message": "Please describe this image.",
            "mode": "ask",
            "image_ids": ["img-1"],
        },
    )

    assert response.status_code == 200
    assert chat_service.prevalidate_mode_requirements.await_args.kwargs["image_ids"] == ["img-1"]
    assert chat_service.chat_stream.call_args.kwargs["agent_policy"] == "yolo"


def test_chat_stream_endpoint_rejects_session_from_another_notebook():
    chat_service = AsyncMock()
    chat_service.prevalidate_mode_requirements = AsyncMock()
    chat_service.chat_stream = Mock()
    session_service = AsyncMock()
    session_service.get_or_raise = AsyncMock(
        return_value=_FakeSession(session_id="session-1", notebook_id="other-notebook")
    )
    policy_service = _PolicyService(policy="yolo", source="notebook")

    client = _build_client(chat_service, session_service, policy_service)
    response = client.post(
        "/api/v1/chat/notebooks/notebook-1/chat/stream",
        json={"session_id": "session-1", "message": "hi", "mode": "agent"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Session does not belong to notebook"
    chat_service.prevalidate_mode_requirements.assert_not_awaited()
    chat_service.chat_stream.assert_not_called()
    assert policy_service.calls == []


def test_confirm_endpoint_returns_200_when_request_is_resolved():
    chat_service = AsyncMock()
    chat_service.confirm_action = AsyncMock(return_value=True)
    session_service = AsyncMock()

    client = _build_client(chat_service, session_service)
    response = client.post(
        "/api/v1/chat/session-1/confirm",
        json={"request_id": "req-1", "approved": True},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "resolved"}


def test_confirm_endpoint_returns_404_when_request_is_missing():
    chat_service = AsyncMock()
    chat_service.confirm_action = AsyncMock(return_value=False)
    session_service = AsyncMock()

    client = _build_client(chat_service, session_service)
    response = client.post(
        "/api/v1/chat/session-1/confirm",
        json={"request_id": "missing", "approved": False},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Confirmation request not found"


def test_sse_adapter_emits_phase_and_thinking_compat_events():
    async def _stream():
        yield {"type": "phase", "stage": "reasoning"}

    async def _collect():
        items = []
        async for payload in chat_router.sse_adapter(_stream()):
            items.append(payload)
        return items

    events = asyncio.run(_collect())
    parsed = [json.loads(item.removeprefix("data: ").strip()) for item in events]

    assert parsed == [
        {"type": "phase", "stage": "reasoning"},
        {"type": "thinking", "stage": "reasoning"},
    ]


def test_sse_adapter_passthroughs_intermediate_content_events():
    async def _stream():
        yield {"type": "intermediate_content", "delta": "让我先查一下"}

    async def _collect():
        items = []
        async for payload in chat_router.sse_adapter(_stream()):
            items.append(payload)
        return items

    events = asyncio.run(_collect())
    parsed = [json.loads(item.removeprefix("data: ").strip()) for item in events]

    assert parsed == [{"type": "intermediate_content", "delta": "让我先查一下"}]


def test_heartbeat_generator_emits_heartbeat_while_waiting_for_first_event():
    async def delayed_stream():
        await asyncio.sleep(0.12)
        yield SSEEvent.content("hello")

    async def _collect():
        events = []
        async for event in heartbeat_generator(delayed_stream(), heartbeat_interval=0.05):
            events.append(event)
            if event == SSEEvent.content("hello"):
                break
        return events

    events = asyncio.run(_collect())

    assert events[0] == SSEEvent.heartbeat()
    assert SSEEvent.content("hello") in events
