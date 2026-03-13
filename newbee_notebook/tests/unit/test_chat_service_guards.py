import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from newbee_notebook.application.services.chat_service import ChatService
from newbee_notebook.core.engine.stream_events import ContentEvent, DoneEvent, PhaseEvent, SourceEvent
from newbee_notebook.core.session import SessionRunResult
from newbee_notebook.core.tools.contracts import SourceItem
from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.domain.value_objects.mode_type import MessageRole, ModeType
from newbee_notebook.exceptions import DocumentProcessingError


class _CancelledInnerStream:
    def __init__(self):
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise asyncio.CancelledError()

    async def aclose(self):
        self.closed = True


class _DummyCancelledRuntimeSessionManager:
    def __init__(self):
        self.inner_stream = _CancelledInnerStream()

    async def start_session(self, session_id: str):
        return None

    def chat_stream(self, **kwargs):
        return self.inner_stream

    def get_last_sources(self):
        return []


class _DummyRuntimeSessionManager:
    def __init__(self):
        self.started_with: list[str] = []
        self.chat_kwargs = None
        self.stream_kwargs = None

    async def start_session(self, session_id: str):
        self.started_with.append(session_id)

    async def chat(self, **kwargs):
        self.chat_kwargs = kwargs
        return SessionRunResult(
            content="runtime answer",
            sources=[
                SourceItem(
                    document_id="doc-1",
                    chunk_id="chunk-1",
                    title="Doc 1",
                    text="runtime source",
                    score=0.8,
                    source_type="retrieval",
                )
            ],
        )

    async def chat_stream(self, **kwargs):
        self.stream_kwargs = kwargs
        yield PhaseEvent(stage="reasoning")
        yield ContentEvent(delta="hello ")
        yield ContentEvent(delta="agent")
        yield SourceEvent(
            sources=[
                SourceItem(
                    document_id="doc-1",
                    chunk_id="chunk-1",
                    title="Doc 1",
                    text="runtime source",
                    score=0.8,
                    source_type="retrieval",
                )
            ]
        )
        yield DoneEvent()


def _build_service(ref_repo=None, document_repo=None):
    return ChatService(
        session_repo=AsyncMock(),
        notebook_repo=AsyncMock(),
        reference_repo=AsyncMock(),
        document_repo=document_repo or AsyncMock(),
        ref_repo=ref_repo or AsyncMock(),
        message_repo=AsyncMock(),
        session_manager=_DummyRuntimeSessionManager(),
    )


def test_chat_service_can_be_built_without_legacy_session_manager():
    service = ChatService(
        session_repo=AsyncMock(),
        notebook_repo=AsyncMock(),
        reference_repo=AsyncMock(),
        document_repo=AsyncMock(),
        ref_repo=AsyncMock(),
        message_repo=AsyncMock(),
        session_manager=_DummyRuntimeSessionManager(),
    )

    assert service is not None


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


def test_filter_sources_by_mode_quality_keeps_ask_sources_when_scores_absent():
    sources = [
        {"document_id": "doc-1", "chunk_id": "c1", "text": "a", "score": 0.0},
        {"document_id": "doc-1", "chunk_id": "c2", "text": "b"},
    ]

    filtered = ChatService._filter_sources_by_mode_quality(sources, ModeType.ASK)

    assert filtered == sources


def test_validate_mode_guard_allows_ask_when_completed_docs_exist():
    service = _build_service()

    asyncio.run(
        service._validate_mode_guard(
            mode_enum=ModeType.ASK,
            allowed_doc_ids=["doc-1"],
            context=None,
            notebook_id="nb-1",
            documents_by_status={"processing": 1, "completed": 1},
            blocking_document_ids=["doc-2"],
        )
    )


def test_validate_mode_guard_blocks_explain_when_target_document_is_not_completed():
    service = _build_service()

    with pytest.raises(DocumentProcessingError) as exc_info:
        asyncio.run(
            service._validate_mode_guard(
                mode_enum=ModeType.EXPLAIN,
                allowed_doc_ids=["doc-1"],
                context={"selected_text": "focus", "document_id": "doc-2"},
                notebook_id="nb-1",
                documents_by_status={"completed": 1, "processing": 1},
                blocking_document_ids=["doc-2"],
            )
        )

    exc = exc_info.value
    assert exc.error_code == "E4001"
    assert exc.http_status == 409
    assert exc.details["document_id"] == "doc-2"


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


def test_apply_source_filter_logs_excluded_non_completed_doc_ids(caplog):
    service = _build_service()

    with caplog.at_level(logging.INFO):
        filtered = service._apply_source_filter(["doc-1"], ["doc-2", "doc-1", "doc-3"])

    assert filtered == ["doc-1"]
    assert "excluded 2 non-completed doc(s)" in caplog.text
    assert "doc-2" in caplog.text
    assert "doc-3" in caplog.text


def test_build_blocking_warning_returns_payload_for_partial_scope():
    warning = ChatService._build_blocking_warning(
        blocking_doc_ids=["doc-2", "doc-3"],
        allowed_doc_ids=["doc-1"],
        docs_by_status={"completed": 1, "processing": 1, "pending": 1},
    )

    assert warning == {
        "type": "warning",
        "code": "partial_documents",
        "message": "2 个文档正在处理中，当前检索范围不包含这些文档",
        "details": {
            "blocking_document_ids": ["doc-2", "doc-3"],
            "available_document_count": 1,
            "documents_by_status": {"completed": 1, "processing": 1, "pending": 1},
        },
    }


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
    service = ChatService(
        session_repo=session_repo,
        notebook_repo=AsyncMock(),
        reference_repo=reference_repo,
        document_repo=document_repo,
        ref_repo=ref_repo,
        message_repo=message_repo,
        session_manager=_DummyRuntimeSessionManager(),
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

    assert observed_types[:2] == ["start", "phase"]
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
        session_manager=_DummyRuntimeSessionManager(),
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
    assert ("phase", "reasoning") in observed
    assert any(event_type == "content" for event_type, _ in observed)


def test_chat_stream_emits_warning_before_thinking_for_partial_documents():
    session_repo = AsyncMock()
    session_repo.get.return_value = SimpleNamespace(
        session_id="session-1",
        notebook_id="nb-1",
        message_count=0,
        include_ec_context=False,
    )

    ref_repo = AsyncMock()
    ref_repo.list_by_notebook.return_value = [
        SimpleNamespace(document_id="doc-1"),
        SimpleNamespace(document_id="doc-2"),
    ]
    document_repo = AsyncMock()
    document_repo.get_batch.return_value = [
        SimpleNamespace(document_id="doc-1", status=DocumentStatus.COMPLETED, title="Ready"),
        SimpleNamespace(document_id="doc-2", status=DocumentStatus.PROCESSING, title="Busy"),
    ]
    document_repo.get.return_value = SimpleNamespace(document_id="doc-1")

    service = ChatService(
        session_repo=session_repo,
        notebook_repo=AsyncMock(),
        reference_repo=AsyncMock(),
        document_repo=document_repo,
        ref_repo=ref_repo,
        message_repo=AsyncMock(),
        session_manager=_DummyRuntimeSessionManager(),
    )

    async def _collect():
        observed = []
        async for event in service.chat_stream(session_id="session-1", message="hi", mode="ask"):
            observed.append(event)
            if event["type"] == "done":
                break
        return observed

    observed = asyncio.run(_collect())
    assert observed[0]["type"] == "start"
    assert observed[1]["type"] == "warning"
    assert observed[2] == {"type": "phase", "stage": "reasoning"}


def test_chat_returns_warnings_for_partial_documents_in_nonstream_mode():
    session_repo = AsyncMock()
    session_repo.get.return_value = SimpleNamespace(
        session_id="session-1",
        notebook_id="nb-1",
        message_count=0,
        include_ec_context=False,
    )

    ref_repo = AsyncMock()
    ref_repo.list_by_notebook.return_value = [
        SimpleNamespace(document_id="doc-1"),
        SimpleNamespace(document_id="doc-2"),
    ]
    document_repo = AsyncMock()
    document_repo.get_batch.return_value = [
        SimpleNamespace(document_id="doc-1", status=DocumentStatus.COMPLETED, title="Ready"),
        SimpleNamespace(document_id="doc-2", status=DocumentStatus.PROCESSING, title="Busy"),
    ]

    service = ChatService(
        session_repo=session_repo,
        notebook_repo=AsyncMock(),
        reference_repo=AsyncMock(),
        document_repo=document_repo,
        ref_repo=ref_repo,
        message_repo=AsyncMock(),
        session_manager=_DummyRuntimeSessionManager(),
    )

    result = asyncio.run(service.chat(session_id="session-1", message="hi", mode="ask"))

    assert result.warnings == [
        {
            "type": "warning",
            "code": "partial_documents",
            "message": "1 个文档正在处理中，当前检索范围不包含这些文档",
            "details": {
                "blocking_document_ids": ["doc-2"],
                "available_document_count": 1,
                "documents_by_status": {
                    "uploaded": 0,
                    "pending": 0,
                    "processing": 1,
                    "converted": 0,
                    "completed": 1,
                    "failed": 0,
                },
            },
        }
    ]


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

    session_manager = _DummyCancelledRuntimeSessionManager()

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

def test_chat_routes_chat_alias_through_runtime_agent_and_persists_agent_mode():
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
        session_manager=_DummyRuntimeSessionManager(),
    )

    result = asyncio.run(service.chat(session_id="session-1", message="hi", mode="chat"))

    assert result.content == "runtime answer"
    assert result.mode == ModeType.AGENT
    assert service._session_manager.started_with == ["session-1"]
    assert service._session_manager.chat_kwargs["mode_type"] == ModeType.AGENT
    persisted = message_repo.create_batch.await_args.args[0]
    assert persisted[0].mode == ModeType.AGENT
    assert persisted[0].role == MessageRole.USER
    assert persisted[1].mode == ModeType.AGENT
    assert result.sources[0].document_id == "doc-1"


def test_chat_stream_emits_phase_events_for_runtime_agent_mode():
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
    service = ChatService(
        session_repo=session_repo,
        notebook_repo=AsyncMock(),
        reference_repo=AsyncMock(),
        document_repo=document_repo,
        ref_repo=ref_repo,
        message_repo=AsyncMock(),
        session_manager=_DummyRuntimeSessionManager(),
    )

    async def _collect():
        observed = []
        async for event in service.chat_stream(session_id="session-1", message="hi", mode="chat"):
            observed.append(event)
            if event["type"] == "done":
                break
        return observed

    observed = asyncio.run(_collect())

    assert observed[0] == {"type": "start", "message_id": 1}
    assert observed[1] == {"type": "phase", "stage": "reasoning"}
    assert observed[2] == {"type": "content", "delta": "hello "}
    assert observed[3] == {"type": "content", "delta": "agent"}
    assert observed[4]["type"] == "sources"
    assert observed[4]["sources"][0]["source_type"] == "retrieval"
    assert observed[5] == {"type": "done"}


def test_chat_routes_explain_to_runtime_manager_with_selected_text_context():
    session_repo = AsyncMock()
    session_repo.get.return_value = SimpleNamespace(
        session_id="session-1",
        notebook_id="nb-1",
        message_count=0,
        include_ec_context=False,
    )
    ref_repo = AsyncMock()
    ref_repo.list_by_notebook.return_value = [SimpleNamespace(document_id="doc-1")]
    document_repo = AsyncMock()
    document_repo.get_batch.return_value = [
        SimpleNamespace(document_id="doc-1", status=DocumentStatus.COMPLETED, title="Ready"),
    ]
    document_repo.get.return_value = SimpleNamespace(document_id="doc-1")
    service = ChatService(
        session_repo=session_repo,
        notebook_repo=AsyncMock(),
        reference_repo=AsyncMock(),
        document_repo=document_repo,
        ref_repo=ref_repo,
        message_repo=AsyncMock(),
        session_manager=_DummyRuntimeSessionManager(),
    )

    result = asyncio.run(
        service.chat(
            session_id="session-1",
            message="explain this",
            mode="explain",
            context={"selected_text": "focus", "document_id": "doc-1"},
        )
    )

    assert result.content == "runtime answer"
    assert result.mode == ModeType.EXPLAIN
    assert service._session_manager.chat_kwargs["mode_type"] == ModeType.EXPLAIN
    assert service._session_manager.chat_kwargs["context"]["selected_text"] == "focus"
