from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from newbee_notebook.api.dependencies import get_document_repo
from newbee_notebook.api.routers import admin as admin_router
from newbee_notebook.domain.entities.document import Document
from newbee_notebook.domain.value_objects.document_status import DocumentStatus


def _build_client(monkeypatch):
    app = FastAPI()
    app.include_router(admin_router.router, prefix="/api/v1")

    repo = AsyncMock()

    async def _get_repo_override():
        return repo

    app.dependency_overrides[get_document_repo] = _get_repo_override

    convert_task = SimpleNamespace(delay=MagicMock())
    index_task = SimpleNamespace(delay=MagicMock())
    process_task = SimpleNamespace(delay=MagicMock())
    convert_pending_task = SimpleNamespace(delay=MagicMock())
    index_pending_task = SimpleNamespace(delay=MagicMock())
    process_pending_task = SimpleNamespace(delay=MagicMock())

    monkeypatch.setattr(admin_router, "convert_document_task", convert_task)
    monkeypatch.setattr(admin_router, "index_document_task", index_task)
    monkeypatch.setattr(admin_router, "process_document_task", process_task)
    monkeypatch.setattr(admin_router, "convert_pending_task", convert_pending_task)
    monkeypatch.setattr(admin_router, "index_pending_task", index_pending_task)
    monkeypatch.setattr(admin_router, "process_pending_documents_task", process_pending_task)

    return (
        TestClient(app),
        repo,
        convert_task,
        index_task,
        process_task,
        convert_pending_task,
        index_pending_task,
        process_pending_task,
    )


def test_convert_document_queues_task(monkeypatch):
    (
        client,
        repo,
        convert_task,
        _index_task,
        _process_task,
        _convert_pending_task,
        _index_pending_task,
        _process_pending_task,
    ) = _build_client(monkeypatch)

    repo.get.return_value = Document(
        document_id="doc-1",
        title="doc",
        library_id="lib-1",
        status=DocumentStatus.UPLOADED,
    )

    response = client.post("/api/v1/admin/documents/doc-1/convert")
    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "convert_only"
    convert_task.delay.assert_called_once_with("doc-1", force=False)


def test_index_document_requires_conversion(monkeypatch):
    (
        client,
        repo,
        _convert_task,
        _index_task,
        _process_task,
        _convert_pending_task,
        _index_pending_task,
        _process_pending_task,
    ) = _build_client(monkeypatch)

    repo.get.return_value = Document(
        document_id="doc-2",
        title="doc",
        library_id="lib-1",
        status=DocumentStatus.UPLOADED,
    )

    response = client.post("/api/v1/admin/documents/doc-2/index")
    assert response.status_code == 400


def test_reindex_prefers_index_only_when_conversion_preserved(monkeypatch):
    (
        client,
        repo,
        _convert_task,
        index_task,
        process_task,
        _convert_pending_task,
        _index_pending_task,
        _process_pending_task,
    ) = _build_client(monkeypatch)

    repo.get.return_value = Document(
        document_id="doc-3",
        title="doc",
        library_id="lib-1",
        status=DocumentStatus.FAILED,
        content_path="documents/doc-3/markdown/content.md",
    )

    response = client.post("/api/v1/admin/documents/doc-3/reindex")
    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "index_only"
    index_task.delay.assert_called_once_with("doc-3", force=True)
    process_task.delay.assert_not_called()


def test_convert_pending_dry_run_returns_filtered_ids(monkeypatch):
    (
        client,
        repo,
        _convert_task,
        _index_task,
        _process_task,
        convert_pending_task,
        _index_pending_task,
        _process_pending_task,
    ) = _build_client(monkeypatch)

    docs_by_status = {
        DocumentStatus.UPLOADED: [
            Document(document_id="doc-u-1", title="u1", library_id="lib-1", status=DocumentStatus.UPLOADED),
            Document(document_id="doc-u-2", title="u2", library_id="lib-1", status=DocumentStatus.UPLOADED),
        ],
        DocumentStatus.FAILED: [
            Document(document_id="doc-f-1", title="f1", library_id="lib-1", status=DocumentStatus.FAILED),
        ],
    }

    async def _list_by_library(limit=50, offset=0, status=None):  # noqa: ARG001
        return docs_by_status.get(status, []) if offset == 0 else []

    repo.list_by_library.side_effect = _list_by_library

    response = client.post(
        "/api/v1/admin/convert-pending",
        json={"document_ids": ["doc-u-2", "doc-f-1"], "dry_run": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["queued_count"] == 2
    assert payload["document_ids"] == ["doc-u-2", "doc-f-1"]
    convert_pending_task.delay.assert_not_called()

