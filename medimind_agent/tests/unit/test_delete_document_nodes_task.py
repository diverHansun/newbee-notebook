import asyncio
from unittest.mock import AsyncMock, patch

from medimind_agent.infrastructure.tasks import document_tasks


def test_delete_document_nodes_task_calls_delete_ref_doc(monkeypatch):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    mock_pg = AsyncMock()
    mock_es = AsyncMock()

    document_tasks._EMBED_MODEL = object()
    document_tasks._PG_INDEX = mock_pg
    document_tasks._ES_INDEX = mock_es

    loop.run_until_complete(document_tasks._delete_document_nodes_async("doc-123"))

    mock_pg.delete_ref_doc.assert_awaited_with("doc-123")
    mock_es.delete_ref_doc.assert_awaited_with("doc-123")
