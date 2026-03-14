import asyncio
from unittest.mock import AsyncMock, MagicMock

from newbee_notebook.infrastructure.tasks import document_tasks


def test_index_pg_nodes_uses_db_synced_embedding_provider(monkeypatch):
    sync_mock = AsyncMock(
        return_value={
            "provider": "qwen3-embedding",
            "mode": "local",
            "model_path": "D:/Projects/notebook-project/newbee-notebook/models/Qwen3-Embedding-0.6B",
        }
    )
    load_pg_mock = AsyncMock(return_value=MagicMock())

    monkeypatch.setattr(document_tasks, "sync_embedding_runtime_env_from_db", sync_mock)
    monkeypatch.setattr(document_tasks, "build_embedding", lambda: object())
    monkeypatch.setattr(document_tasks, "load_pgvector_index", load_pg_mock)
    monkeypatch.setattr(document_tasks, "get_storage_config", lambda: {})
    monkeypatch.setattr(
        document_tasks,
        "get_pgvector_config_for_provider",
        lambda provider: {"table_name": f"table_{provider}", "embedding_dimension": 1024},
    )
    monkeypatch.setattr(document_tasks, "_close_vector_index", AsyncMock())

    asyncio.run(document_tasks._index_pg_nodes(["node-1"], session=object()))

    sync_mock.assert_awaited_once()
    assert load_pg_mock.await_args.args[1].table_name == "table_qwen3-embedding"


def test_delete_document_nodes_uses_db_synced_embedding_provider(monkeypatch):
    sync_mock = AsyncMock(return_value={"provider": "zhipu", "mode": None})
    load_pg_mock = AsyncMock(return_value=MagicMock())
    load_es_mock = AsyncMock(return_value=MagicMock())

    monkeypatch.setattr(document_tasks, "sync_embedding_runtime_env_from_db", sync_mock)
    monkeypatch.setattr(document_tasks, "build_embedding", lambda: object())
    monkeypatch.setattr(document_tasks, "load_pgvector_index", load_pg_mock)
    monkeypatch.setattr(document_tasks, "load_es_index", load_es_mock)
    monkeypatch.setattr(document_tasks, "get_storage_config", lambda: {})
    monkeypatch.setattr(
        document_tasks,
        "get_pgvector_config_for_provider",
        lambda provider: {"table_name": f"table_{provider}", "embedding_dimension": 1024},
    )
    monkeypatch.setattr(document_tasks, "_close_vector_index", AsyncMock())

    class _DummySessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _DummyDb:
        def session(self):
            return _DummySessionContext()

    monkeypatch.setattr(document_tasks, "get_database", AsyncMock(return_value=_DummyDb()))

    asyncio.run(document_tasks._delete_document_nodes_async("doc-123"))

    sync_mock.assert_awaited_once()
    assert load_pg_mock.await_args.args[1].table_name == "table_zhipu"
