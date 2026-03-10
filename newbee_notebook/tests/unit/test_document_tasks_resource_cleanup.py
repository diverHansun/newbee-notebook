import asyncio
from unittest.mock import AsyncMock

from newbee_notebook.infrastructure.tasks import document_tasks


class _FakeAsyncCloser:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class _FakeVectorStoreWithNestedAsyncClose:
    def __init__(self) -> None:
        self._store = _FakeAsyncCloser()


class _FakeVectorStoreWithAsyncClose:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class _FakeIndex:
    def __init__(self, *, vector_store) -> None:
        self.vector_store = vector_store
        self.inserted_nodes = None
        self.deleted_doc_id = None

    def insert_nodes(self, nodes) -> None:
        self.inserted_nodes = nodes

    def delete_ref_doc(self, document_id: str) -> None:
        self.deleted_doc_id = document_id


def test_index_es_nodes_closes_nested_async_vector_store(monkeypatch):
    fake_index = _FakeIndex(vector_store=_FakeVectorStoreWithNestedAsyncClose())

    monkeypatch.setattr(document_tasks, "build_embedding", lambda: object())
    monkeypatch.setattr(document_tasks, "load_es_index", AsyncMock(return_value=fake_index))
    monkeypatch.setattr(document_tasks, "get_storage_config", lambda: {})

    asyncio.run(document_tasks._index_es_nodes(["node-1"]))

    assert fake_index.inserted_nodes == ["node-1"]
    assert fake_index.vector_store._store.closed is True


def test_delete_document_nodes_task_closes_loaded_indexes(monkeypatch):
    fake_pg = _FakeIndex(vector_store=_FakeVectorStoreWithAsyncClose())
    fake_es = _FakeIndex(vector_store=_FakeVectorStoreWithNestedAsyncClose())

    monkeypatch.setattr(document_tasks, "build_embedding", lambda: object())
    monkeypatch.setattr(document_tasks, "load_pgvector_index", AsyncMock(return_value=fake_pg))
    monkeypatch.setattr(document_tasks, "load_es_index", AsyncMock(return_value=fake_es))
    monkeypatch.setattr(document_tasks, "get_storage_config", lambda: {})
    monkeypatch.setattr(document_tasks, "get_embedding_provider", lambda: "zhipu")
    monkeypatch.setattr(
        document_tasks,
        "get_pgvector_config_for_provider",
        lambda _provider: {"table_name": "documents_zhipu", "embedding_dimension": 1024},
    )

    asyncio.run(document_tasks._delete_document_nodes_async("doc-123"))

    assert fake_pg.deleted_doc_id == "doc-123"
    assert fake_es.deleted_doc_id == "doc-123"
    assert fake_pg.vector_store.closed is True
    assert fake_es.vector_store._store.closed is True
