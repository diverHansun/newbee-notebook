import asyncio
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from newbee_notebook.api.dependencies import get_chat_service, get_session_service
from newbee_notebook.api.routers import chat as chat_router
from newbee_notebook.api.routers.chat import SSEEvent, heartbeat_generator
from newbee_notebook.exceptions import DocumentProcessingError


def test_sse_event_thinking_formats_stage():
    assert SSEEvent.thinking("searching") == 'data: {"type": "thinking", "stage": "searching"}\n\n'


def test_sse_event_warning_formats_payload():
    assert SSEEvent.warning(
        "partial_documents",
        "1 个文档正在处理中，当前检索范围不包含这些文档",
        {"blocking_document_ids": ["doc-2"]},
    ) == (
        'data: {"type": "warning", "code": "partial_documents", '
        '"message": "1 个文档正在处理中，当前检索范围不包含这些文档", '
        '"details": {"blocking_document_ids": ["doc-2"]}}\n\n'
    )


def _build_client(chat_service: AsyncMock, session_service: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(chat_router.router, prefix="/api/v1")

    async def _override_chat():
        return chat_service

    async def _override_session():
        return session_service

    app.dependency_overrides[get_chat_service] = _override_chat
    app.dependency_overrides[get_session_service] = _override_session
    return TestClient(app)


def test_chat_endpoint_returns_409_for_document_processing_error():
    chat_service = AsyncMock()
    chat_service.chat = AsyncMock(
        side_effect=DocumentProcessingError("所有文档正在处理中，暂无可用的检索数据")
    )
    session_service = AsyncMock()
    session_service.get_or_raise = AsyncMock(return_value=object())

    client = _build_client(chat_service, session_service)
    response = client.post(
        "/api/v1/chat/notebooks/notebook-1/chat",
        json={"session_id": "session-1", "message": "hi", "mode": "ask"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "所有文档正在处理中，暂无可用的检索数据"


def test_chat_stream_endpoint_returns_409_for_document_processing_error():
    chat_service = AsyncMock()
    chat_service.prevalidate_mode_requirements = AsyncMock(
        side_effect=DocumentProcessingError("该文档索引尚未构建完成，暂时无法进行解释/总结")
    )
    session_service = AsyncMock()
    session_service.get_or_raise = AsyncMock(return_value=object())

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
    assert response.json()["detail"] == "该文档索引尚未构建完成，暂时无法进行解释/总结"


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
