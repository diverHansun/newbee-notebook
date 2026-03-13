"""Focused tests for batch-2 runtime chat routing."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from newbee_notebook.application.services.chat_service import ChatService
from newbee_notebook.core.session import SessionRunResult
from newbee_notebook.core.tools.contracts import SourceItem
from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.domain.value_objects.mode_type import ModeType


class _DummyRuntimeAskSessionManager:
    def __init__(self):
        self.started_with: list[str] = []
        self.chat_kwargs = None

    async def start_session(self, session_id: str):
        self.started_with.append(session_id)

    async def chat(self, **kwargs):
        self.chat_kwargs = kwargs
        return SessionRunResult(
            content="runtime ask answer",
            sources=[
                SourceItem(
                    document_id="doc-1",
                    chunk_id="chunk-1",
                    title="Doc 1",
                    text="runtime ask source",
                    score=0.91,
                    source_type="retrieval",
                )
            ],
        )


def test_chat_service_routes_ask_to_runtime_manager():
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
        SimpleNamespace(document_id="doc-1", status=DocumentStatus.COMPLETED, title="Doc 1")
    ]
    document_repo.get.return_value = SimpleNamespace(document_id="doc-1")
    message_repo = AsyncMock()
    runtime_manager = _DummyRuntimeAskSessionManager()

    service = ChatService(
        session_repo=session_repo,
        notebook_repo=AsyncMock(),
        reference_repo=AsyncMock(),
        document_repo=document_repo,
        ref_repo=ref_repo,
        message_repo=message_repo,
        session_manager=runtime_manager,
    )

    result = asyncio.run(service.chat(session_id="session-1", message="hi", mode="ask"))

    assert result.content == "runtime ask answer"
    assert result.mode == ModeType.ASK
    assert runtime_manager.started_with == ["session-1"]
    assert runtime_manager.chat_kwargs["mode_type"] == ModeType.ASK
