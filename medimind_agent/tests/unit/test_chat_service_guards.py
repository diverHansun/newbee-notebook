import asyncio
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
        SimpleNamespace(document_id="doc-1", status=DocumentStatus.COMPLETED),
        SimpleNamespace(document_id="doc-2", status=DocumentStatus.PROCESSING),
        SimpleNamespace(document_id="doc-3", status=DocumentStatus.PENDING),
    ]

    service = _build_service(ref_repo=ref_repo, document_repo=document_repo)
    completed, counts, blocking = asyncio.run(service._get_notebook_scope("nb-1"))

    assert completed == ["doc-1"]
    assert counts["completed"] == 1
    assert counts["processing"] == 1
    assert counts["pending"] == 1
    assert sorted(blocking) == ["doc-2", "doc-3"]


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

