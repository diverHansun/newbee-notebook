import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from medimind_agent.application.services.chat_service import ChatService
from medimind_agent.domain.value_objects.document_status import DocumentStatus
from medimind_agent.domain.value_objects.mode_type import ModeType
from medimind_agent.exceptions import DocumentProcessingError


class _DummySessionManager:
    def __init__(self):
        self.vector_index = object()


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
    ]

    document_repo = AsyncMock()
    document_repo.get_batch.return_value = [
        SimpleNamespace(document_id="doc-1", status=DocumentStatus.COMPLETED, title="Doc 1"),
        SimpleNamespace(document_id="doc-2", status=DocumentStatus.PROCESSING, title="Doc 2"),
        SimpleNamespace(document_id="doc-3", status=DocumentStatus.PENDING, title="Doc 3"),
    ]

    service = _build_service(ref_repo=ref_repo, document_repo=document_repo)
    completed, counts, blocking, titles = asyncio.run(service._get_notebook_scope("nb-1"))

    assert completed == ["doc-1"]
    assert counts["completed"] == 1
    assert counts["processing"] == 1
    assert counts["pending"] == 1
    assert sorted(blocking) == ["doc-2", "doc-3"]
    assert titles == {"doc-1": "Doc 1"}


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
