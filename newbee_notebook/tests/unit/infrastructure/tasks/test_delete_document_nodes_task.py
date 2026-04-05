import asyncio
from unittest.mock import AsyncMock, MagicMock
from llama_index.core.vector_stores import FilterOperator

from newbee_notebook.infrastructure.tasks import document_tasks


def test_delete_document_nodes_task_deletes_by_stable_source_document_id(monkeypatch):
    mock_pg_store = MagicMock()
    mock_es_store = MagicMock()
    mock_pg = MagicMock(vector_store=mock_pg_store)
    mock_es = MagicMock(vector_store=mock_es_store)

    class _DummySessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _DummyDb:
        def session(self):
            return _DummySessionContext()

    monkeypatch.setattr(
        document_tasks,
        "sync_embedding_runtime_env_from_db",
        AsyncMock(return_value={"provider": "zhipu", "mode": None}),
    )
    monkeypatch.setattr(document_tasks, "build_embedding", lambda: object())
    monkeypatch.setattr(document_tasks, "load_pgvector_index", AsyncMock(return_value=mock_pg))
    monkeypatch.setattr(document_tasks, "load_es_index", AsyncMock(return_value=mock_es))
    monkeypatch.setattr(document_tasks, "get_storage_config", lambda: {})
    monkeypatch.setattr(document_tasks, "get_database", AsyncMock(return_value=_DummyDb()))
    monkeypatch.setattr(
        document_tasks,
        "get_pgvector_config_for_provider",
        lambda _provider: {"table_name": "documents_zhipu", "embedding_dimension": 1024},
    )

    asyncio.run(document_tasks._delete_document_nodes_async("doc-123"))

    pg_filters = mock_pg_store.delete_nodes.call_args.kwargs["filters"]
    es_filters = mock_es_store.delete_nodes.call_args.kwargs["filters"]
    assert pg_filters.filters[0].key == "source_document_id"
    assert pg_filters.filters[0].operator == FilterOperator.EQ
    assert pg_filters.filters[0].value == "doc-123"
    assert es_filters.filters[0].key == "source_document_id"
    assert es_filters.filters[0].operator == FilterOperator.EQ
    assert es_filters.filters[0].value == "doc-123"
