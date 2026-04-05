from datetime import datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from newbee_notebook.api.dependencies import get_note_service
from newbee_notebook.api.routers import notes as notes_router
from newbee_notebook.domain.entities.note import Note


def _build_client(service: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(notes_router.router, prefix="/api/v1")

    async def _override():
        return service

    app.dependency_overrides[get_note_service] = _override
    return TestClient(app)


def test_create_note_returns_201():
    service = AsyncMock()
    service.create = AsyncMock(
        return_value=Note(
            note_id="note-1",
            notebook_id="nb-1",
            title="Title",
            content="Body",
            document_ids=["doc-1"],
            mark_ids=["mark-1"],
            created_at=datetime(2026, 3, 19, 12, 0, 0),
            updated_at=datetime(2026, 3, 19, 12, 0, 0),
        )
    )

    client = _build_client(service)
    response = client.post(
        "/api/v1/notes",
        json={
            "notebook_id": "nb-1",
            "title": "Title",
            "content": "Body",
            "document_ids": ["doc-1"],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["note_id"] == "note-1"
    assert payload["notebook_id"] == "nb-1"
    assert payload["document_ids"] == ["doc-1"]


def test_list_notes_returns_compact_items():
    service = AsyncMock()
    service.list_by_notebook_paginated = AsyncMock(
        return_value=([
            Note(
                note_id="note-1",
                notebook_id="nb-1",
                title="Title",
                content="Body",
                document_ids=["doc-1"],
                mark_ids=["mark-1", "mark-2"],
            )
        ], 1)
    )

    client = _build_client(service)
    response = client.get("/api/v1/notebooks/nb-1/notes")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["pagination"] == {
        "total": 1,
        "limit": 20,
        "offset": 0,
        "has_next": False,
        "has_prev": False,
    }
    assert payload["notes"][0]["note_id"] == "note-1"
    assert payload["notes"][0]["mark_count"] == 2
    assert "content" not in payload["notes"][0]


def test_list_all_notes_returns_pagination():
    service = AsyncMock()
    service.list_all_paginated = AsyncMock(
        return_value=(
            [
                Note(
                    note_id="note-1",
                    notebook_id="nb-1",
                    title="Title",
                    content="Body",
                    document_ids=["doc-1"],
                    mark_ids=["mark-1"],
                )
            ],
            3,
        )
    )

    client = _build_client(service)
    response = client.get("/api/v1/notes?limit=1&offset=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["pagination"] == {
        "total": 3,
        "limit": 1,
        "offset": 1,
        "has_next": True,
        "has_prev": True,
    }
    service.list_all_paginated.assert_awaited_once_with(
        document_id=None,
        sort_by="updated_at",
        order="desc",
        limit=1,
        offset=1,
    )


def test_get_note_returns_detail():
    service = AsyncMock()
    service.get_or_raise = AsyncMock(
        return_value=Note(
            note_id="note-1",
            notebook_id="nb-1",
            title="Title",
            content="Body",
            document_ids=["doc-1"],
            mark_ids=["mark-1"],
        )
    )

    client = _build_client(service)
    response = client.get("/api/v1/notes/note-1")

    assert response.status_code == 200
    assert response.json()["mark_ids"] == ["mark-1"]


def test_patch_note_returns_updated_note():
    service = AsyncMock()
    service.update = AsyncMock(
        return_value=Note(
            note_id="note-1",
            notebook_id="nb-1",
            title="New",
            content="Updated",
            document_ids=["doc-1"],
            mark_ids=["mark-1"],
        )
    )

    client = _build_client(service)
    response = client.patch("/api/v1/notes/note-1", json={"title": "New", "content": "Updated"})

    assert response.status_code == 200
    assert response.json()["title"] == "New"


def test_tag_document_returns_204():
    service = AsyncMock()
    service.add_document_tag = AsyncMock(return_value=None)

    client = _build_client(service)
    response = client.post("/api/v1/notes/note-1/documents", json={"document_id": "doc-1"})

    assert response.status_code == 204
    service.add_document_tag.assert_awaited_once_with("note-1", "doc-1")


def test_delete_note_returns_204():
    service = AsyncMock()
    service.delete = AsyncMock(return_value=True)

    client = _build_client(service)
    response = client.delete("/api/v1/notes/note-1")

    assert response.status_code == 204
    service.delete.assert_awaited_once_with("note-1")
