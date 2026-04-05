from datetime import datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from newbee_notebook.api.dependencies import get_mark_service
from newbee_notebook.api.routers import marks as marks_router
from newbee_notebook.domain.entities.mark import Mark


def _build_client(service: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(marks_router.router, prefix="/api/v1")

    async def _override():
        return service

    app.dependency_overrides[get_mark_service] = _override
    return TestClient(app)


def test_create_mark_returns_201():
    service = AsyncMock()
    service.create = AsyncMock(
        return_value=Mark(
            mark_id="mark-1",
            document_id="doc-1",
            anchor_text="anchor",
            char_offset=5,
            context_text="ctx",
            created_at=datetime(2026, 3, 19, 12, 0, 0),
            updated_at=datetime(2026, 3, 19, 12, 0, 0),
        )
    )

    client = _build_client(service)
    response = client.post(
        "/api/v1/documents/doc-1/marks",
        json={"anchor_text": "anchor", "char_offset": 5, "context_text": "ctx"},
    )

    assert response.status_code == 201
    assert response.json()["mark_id"] == "mark-1"
    assert response.json()["document_id"] == "doc-1"


def test_list_document_marks_returns_total():
    service = AsyncMock()
    service.list_by_document = AsyncMock(
        return_value=[
            Mark(
                mark_id="mark-1",
                document_id="doc-1",
                anchor_text="anchor",
                char_offset=5,
            )
        ]
    )

    client = _build_client(service)
    response = client.get("/api/v1/documents/doc-1/marks")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["marks"][0]["mark_id"] == "mark-1"


def test_list_notebook_marks_accepts_optional_document_filter():
    service = AsyncMock()
    service.list_by_notebook = AsyncMock(return_value=[])

    client = _build_client(service)
    response = client.get("/api/v1/notebooks/notebook-1/marks", params={"document_id": "doc-1"})

    assert response.status_code == 200
    service.list_by_notebook.assert_awaited_once_with("notebook-1", document_id="doc-1")


def test_count_document_marks_returns_count():
    service = AsyncMock()
    service.count_by_document = AsyncMock(return_value=3)

    client = _build_client(service)
    response = client.get("/api/v1/documents/doc-1/marks/count")

    assert response.status_code == 200
    assert response.json() == {"count": 3}


def test_delete_mark_returns_204():
    service = AsyncMock()
    service.delete = AsyncMock(return_value=True)

    client = _build_client(service)
    response = client.delete("/api/v1/marks/mark-1")

    assert response.status_code == 204
    service.delete.assert_awaited_once_with("mark-1")
