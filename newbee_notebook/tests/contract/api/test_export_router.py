from __future__ import annotations

import io
from datetime import datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from newbee_notebook.api.dependencies import get_export_service, get_notebook_service
from newbee_notebook.api.routers import export as export_router
from newbee_notebook.application.services.notebook_service import NotebookNotFoundError
from newbee_notebook.domain.entities.notebook import Notebook


def _build_client(notebook_service: AsyncMock, export_service: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(export_router.router, prefix="/api/v1")

    async def _override_notebook_service():
        return notebook_service

    async def _override_export_service():
        return export_service

    app.dependency_overrides[get_notebook_service] = _override_notebook_service
    app.dependency_overrides[get_export_service] = _override_export_service
    return TestClient(app)


def _make_notebook() -> Notebook:
    return Notebook(
        notebook_id="nb-1",
        title="Notebook Export",
        description="for export",
        created_at=datetime(2026, 4, 15, 9, 0, 0),
        updated_at=datetime(2026, 4, 15, 9, 0, 0),
    )


def test_export_notebook_returns_zip_attachment():
    notebook_service = AsyncMock()
    notebook_service.get_or_raise = AsyncMock(return_value=_make_notebook())

    export_service = AsyncMock()
    export_service.export_notebook = AsyncMock(
        return_value=(io.BytesIO(b"zip-bytes"), "Notebook Export-export-2026-04-15.zip")
    )

    client = _build_client(notebook_service, export_service)
    response = client.get("/api/v1/notebooks/nb-1/export")

    assert response.status_code == 200
    assert response.content == b"zip-bytes"
    assert response.headers["content-type"] == "application/zip"
    assert "attachment;" in response.headers.get("content-disposition", "")
    export_service.export_notebook.assert_awaited_once_with(
        "nb-1",
        {"documents", "notes", "marks", "diagrams", "video_summaries"},
    )


def test_export_notebook_forwards_requested_types():
    notebook_service = AsyncMock()
    notebook_service.get_or_raise = AsyncMock(return_value=_make_notebook())

    export_service = AsyncMock()
    export_service.export_notebook = AsyncMock(
        return_value=(io.BytesIO(b"zip"), "x.zip")
    )

    client = _build_client(notebook_service, export_service)
    response = client.get("/api/v1/notebooks/nb-1/export?types=notes,marks")

    assert response.status_code == 200
    export_service.export_notebook.assert_awaited_once_with("nb-1", {"notes", "marks"})


def test_export_notebook_rejects_invalid_types():
    notebook_service = AsyncMock()
    notebook_service.get_or_raise = AsyncMock(return_value=_make_notebook())

    export_service = AsyncMock()
    export_service.export_notebook = AsyncMock()

    client = _build_client(notebook_service, export_service)
    response = client.get("/api/v1/notebooks/nb-1/export?types=notes,invalid")

    assert response.status_code == 422
    export_service.export_notebook.assert_not_called()


def test_export_notebook_returns_404_when_notebook_missing():
    notebook_service = AsyncMock()
    notebook_service.get_or_raise = AsyncMock(side_effect=NotebookNotFoundError("missing"))

    export_service = AsyncMock()
    export_service.export_notebook = AsyncMock()

    client = _build_client(notebook_service, export_service)
    response = client.get("/api/v1/notebooks/nb-1/export")

    assert response.status_code == 404
    assert response.json()["detail"] == "Notebook not found"
    export_service.export_notebook.assert_not_called()
