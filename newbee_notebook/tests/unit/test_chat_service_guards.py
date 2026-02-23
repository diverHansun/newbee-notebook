import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from newbee_notebook.application.services.chat_service import ChatService
from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.domain.value_objects.mode_type import ModeType
from newbee_notebook.exceptions import DocumentProcessingError


class _DummySessionManager:
    def __init__(self):
        self.vector_index = object()


class _DummyStreamingSessionManager(_DummySessionManager):
    async def start_session(self, session_id: str):
        return None

    async def chat_stream(self, **kwargs):
        yield "hello "
        yield "world"

    def get_last_sources(self):
        return [
            {
                "document_id": "doc-1",
                "chunk_id": "chunk-1",
                "text": "source text",
                "title": "Doc 1",
                "score": 0.9,
            }
        ]


class _DummyPhaseStreamingSessionManager(_DummySessionManager):
    async def start_session(self, session_id: str):
        return None

    async def chat_stream(self, **kwargs):
        yield "__PHASE__:searching"
        yield "__PHASE__:generating"
        yield "hello "
        yield "world"

    def get_last_sources(self):
        return []


class _CancelledInnerStream:
    def __init__(self):
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise asyncio.CancelledError()

    async def aclose(self):
        self.closed = True


class _DummyCancelledStreamingSessionManager(_DummySessionManager):
    def __init__(self):
        super().__init__()
        self.inner_stream = _CancelledInnerStream()

    async def start_session(self, session_id: str):
        return None

    def chat_stream(self, **kwargs):
        return self.inner_stream

    def get_last_sources(self):
        return []


class _DummyNonStreamFailsButStreamWorksSessionManager(_DummySessionManager):
    async def start_session(self, session_id: str):
        return None

    async def chat(self, **kwargs):
        class APIConnectionError(Exception):
            __module__ = "openai"

        raise APIConnectionError("Connection error")

    async def chat_stream(self, **kwargs):
        yield "__PHASE__:searching"
        yield "__PHASE__:generating"
        yield "hello "
        yield "fallback"

    def get_last_sources(self):
        return []


def _build_service(ref_repo=None, document_repo=None):
    return ChatService(
        session_repo=AsyncMock(),
        notebook_repo=AsyncMock(),
        reference_repo=AsyncMock(),
        document_repo=document_repo or AsyncMock(),
        ref_repo=ref_repo or AsyncMock(),
        message_repo=AsyncMock(),
        session_manager=_DummySessionManager(),
    )


def test_get_notebook_scope_returns_completed_and_status_counts():
    ref_repo = AsyncMock()
    ref_repo.list_by_notebook.return_value = [
        SimpleNamespace(document_id="doc-1"),
        SimpleNamespace(document_id="doc-2"),
        SimpleNamespace(document_id="doc-3"),
        SimpleNamespace(document_id="doc-4"),
    ]

    document_repo = AsyncMock()
    document_repo.get_batch.return_value = [
        SimpleNamespace(document_id="doc-1", status=DocumentStatus.COMPLETED, title="Doc 1"),
        SimpleNamespace(document_id="doc-2", status=DocumentStatus.PROCESSING, title="Doc 2"),
        SimpleNamespace(document_id="doc-3", status=DocumentStatus.PENDING, title="Doc 3"),
        SimpleNamespace(document_id="doc-4", status=DocumentStatus.CONVERTED, title="Doc 4"),
    ]

    service = _build_service(ref_repo=ref_repo, document_repo=document_repo)
    completed, counts, blocking, titles = asyncio.run(service._get_notebook_scope("nb-1"))

    assert completed == ["doc-1"]
    assert counts["completed"] == 1
    assert counts["processing"] == 1
    assert counts["pending"] == 1
    assert counts["converted"] == 1
    assert sorted(blocking) == ["doc-2", "doc-3", "doc-4"]
    assert titles == {"doc-1": "Doc 1"}


def test_apply_source_filter_preserves_semantics():
    service = _build_service()
    all_ids = ["doc-1", "doc-2", "doc-3"]

    assert service._apply_source_filter(all_ids, None) == all_ids
    assert service._apply_source_filter(all_ids, []) == []
    assert service._apply_source_filter(all_ids, ["doc-3", "doc-x", "doc-1"]) == ["doc-3", "doc-1"]


def test_validate_mode_guard_raises_document_processing_error_for_ask():
    service = _build_service()

    with pytest.raises(DocumentProcessingError) as exc_info:
        asyncio.run(
            service._validate_mode_guard(
                mode_enum=ModeType.ASK,
                allowed_doc_ids=["doc-1"],
                context=None,
                notebook_id="nb-1",
                documents_by_status={"processing": 1, "completed": 0},
                blocking_document_ids=["doc-2"],
            )
        )

    exc = exc_info.value
    assert exc.error_code == "E4001"
    assert exc.http_status == 409
    assert exc.details["blocking_document_ids"] == ["doc-2"]


def test_validate_mode_guard_keeps_conclude_selected_text_rule():
    service = _build_service()

    with pytest.raises(ValueError):
        asyncio.run(
            service._validate_mode_guard(
                mode_enum=ModeType.CONCLUDE,
                allowed_doc_ids=[],
                context=None,
                notebook_id="nb-1",
                documents_by_status={},
                blocking_document_ids=[],
            )
        )


def test_filter_valid_sources_logs_missing_doc_once(caplog):
    document_repo = AsyncMock()

    async def _get(doc_id: str):
        if doc_id == "doc-ok":
            return SimpleNamespace(document_id="doc-ok")
        return None

    document_repo.get.side_effect = _get
    service = _build_service(document_repo=document_repo)

    sources = [
        {"document_id": "doc-missing", "chunk_id": "c1", "text": "a"},
        {"document_id": "doc-missing", "chunk_id": "c2", "text": "b"},
        {"document_id": "doc-ok", "chunk_id": "c3", "text": "c"},
    ]

    with caplog.at_level(logging.WARNING):
        filtered = asyncio.run(service._filter_valid_sources(sources))

    assert [item["document_id"] for item in filtered] == ["doc-ok"]
    warning_messages = [
        record.getMessage()
        for record in caplog.records
        if "missing document_id: doc-missing" in record.getMessage()
    ]
    assert len(warning_messages) == 1
    assert "Skipping 2 source item(s)" in warning_messages[0]


def test_chat_stream_persists_messages_before_done_event():
    session_repo = AsyncMock()
    session_repo.get.return_value = SimpleNamespace(
        session_id="session-1",
        notebook_id="nb-1",
        message_count=0,
        include_ec_context=False,
    )

    ref_repo = AsyncMock()
    ref_repo.list_by_notebook.return_value = []
    document_repo = AsyncMock()
    document_repo.get_batch.return_value = []
    document_repo.get.return_value = SimpleNamespace(document_id="doc-1")

    message_repo = AsyncMock()
    reference_repo = AsyncMock()
    session_manager = _DummyStreamingSessionManager()

    service = ChatService(
        session_repo=session_repo,
        notebook_repo=AsyncMock(),
        reference_repo=reference_repo,
        document_repo=document_repo,
        ref_repo=ref_repo,
        message_repo=message_repo,
        session_manager=session_manager,
    )

    observed_types: list[str] = []

    async def _consume_until_done():
        async for event in service.chat_stream(session_id="session-1", message="hi", mode="chat"):
            observed_types.append(event["type"])
            if event["type"] == "done":
                assert message_repo.create_batch.await_count == 1
                assert session_repo.increment_message_count.await_count == 1
                assert reference_repo.create_batch.await_count == 1
                break

    asyncio.run(_consume_until_done())

    assert observed_types[:2] == ["start", "content"]
    assert "done" in observed_types


def test_chat_stream_emits_thinking_events_for_phase_markers():
    session_repo = AsyncMock()
    session_repo.get.return_value = SimpleNamespace(
        session_id="session-1",
        notebook_id="nb-1",
        message_count=0,
        include_ec_context=False,
    )

    ref_repo = AsyncMock()
    ref_repo.list_by_notebook.return_value = []
    document_repo = AsyncMock()
    document_repo.get_batch.return_value = []

    service = ChatService(
        session_repo=session_repo,
        notebook_repo=AsyncMock(),
        reference_repo=AsyncMock(),
        document_repo=document_repo,
        ref_repo=ref_repo,
        message_repo=AsyncMock(),
        session_manager=_DummyPhaseStreamingSessionManager(),
    )

    async def _collect_types_and_stages():
        observed = []
        async for event in service.chat_stream(session_id="session-1", message="hi", mode="chat"):
            observed.append((event["type"], event.get("stage")))
            if event["type"] == "done":
                break
        return observed

    observed = asyncio.run(_collect_types_and_stages())
    assert observed[0] == ("start", None)
    assert ("thinking", "searching") in observed
    assert ("thinking", "generating") in observed
    assert any(event_type == "content" for event_type, _ in observed)


def test_chat_stream_closes_upstream_generator_on_cancelled_error():
    session_repo = AsyncMock()
    session_repo.get.return_value = SimpleNamespace(
        session_id="session-1",
        notebook_id="nb-1",
        message_count=0,
        include_ec_context=False,
    )

    ref_repo = AsyncMock()
    ref_repo.list_by_notebook.return_value = []
    document_repo = AsyncMock()
    document_repo.get_batch.return_value = []

    session_manager = _DummyCancelledStreamingSessionManager()

    service = ChatService(
        session_repo=session_repo,
        notebook_repo=AsyncMock(),
        reference_repo=AsyncMock(),
        document_repo=document_repo,
        ref_repo=ref_repo,
        message_repo=AsyncMock(),
        session_manager=session_manager,
    )

    async def _consume():
        events = []
        async for event in service.chat_stream(session_id="session-1", message="hi", mode="chat"):
            events.append(event)
        return events

    events = asyncio.run(_consume())

    assert events == [{"type": "start", "message_id": 1}]
    assert session_manager.inner_stream.closed is True


def test_chat_falls_back_to_aggregated_stream_on_nonstream_transport_error():
    session_repo = AsyncMock()
    session_repo.get.return_value = SimpleNamespace(
        session_id="session-1",
        notebook_id="nb-1",
        message_count=0,
        include_ec_context=False,
    )

    ref_repo = AsyncMock()
    ref_repo.list_by_notebook.return_value = []
    document_repo = AsyncMock()
    document_repo.get_batch.return_value = []

    message_repo = AsyncMock()
    service = ChatService(
        session_repo=session_repo,
        notebook_repo=AsyncMock(),
        reference_repo=AsyncMock(),
        document_repo=document_repo,
        ref_repo=ref_repo,
        message_repo=message_repo,
        session_manager=_DummyNonStreamFailsButStreamWorksSessionManager(),
    )

    result = asyncio.run(service.chat(session_id="session-1", message="hi", mode="chat"))

    assert result.content == "hello fallback"
    assert message_repo.create_batch.await_count == 1
    assert session_repo.increment_message_count.await_count == 1
