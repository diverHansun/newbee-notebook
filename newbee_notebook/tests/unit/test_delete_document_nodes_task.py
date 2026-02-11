import asyncio
from unittest.mock import AsyncMock, MagicMock

from newbee_notebook.infrastructure.tasks import document_tasks


def test_delete_document_nodes_task_calls_delete_ref_doc(monkeypatch):
    mock_pg = MagicMock()
    mock_es = MagicMock()

    monkeypatch.setattr(document_tasks, "build_embedding", lambda: object())
    monkeypatch.setattr(document_tasks, "load_pgvector_index", AsyncMock(return_value=mock_pg))
    monkeypatch.setattr(document_tasks, "load_es_index", AsyncMock(return_value=mock_es))
    monkeypatch.setattr(document_tasks, "get_storage_config", lambda: {})
    monkeypatch.setattr(document_tasks, "get_embedding_provider", lambda: "zhipu")
    monkeypatch.setattr(
        document_tasks,
        "get_pgvector_config_for_provider",
        lambda _provider: {"table_name": "documents_zhipu", "embedding_dimension": 1024},
    )

    asyncio.run(document_tasks._delete_document_nodes_async("doc-123"))

    mock_pg.delete_ref_doc.assert_called_once_with("doc-123")
    mock_es.delete_ref_doc.assert_called_once_with("doc-123")
