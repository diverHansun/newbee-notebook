from pathlib import Path
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from newbee_notebook.api.dependencies import get_document_service
from newbee_notebook.api.routers import documents as documents_router


def _build_client(service: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(documents_router.router, prefix="/api/v1")

    async def _override():
        return service

    app.dependency_overrides[get_document_service] = _override
    return TestClient(app)


def test_download_document_redirects_to_presigned_url():
    service = AsyncMock()
    service.get_download_url = AsyncMock(return_value="http://localhost:9000/presigned-download")
    service.get_download_path = AsyncMock()

    client = _build_client(service)
    response = client.get("/api/v1/documents/11111111-1111-1111-1111-111111111111/download", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "http://localhost:9000/presigned-download"
    service.get_download_path.assert_not_awaited()


def test_asset_document_redirects_to_presigned_url():
    service = AsyncMock()
    service.get_asset_url = AsyncMock(return_value="http://localhost:9000/presigned-asset")
    service.get_asset_path = AsyncMock()

    client = _build_client(service)
    response = client.get(
        "/api/v1/documents/11111111-1111-1111-1111-111111111111/assets/images/demo.jpg",
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == "http://localhost:9000/presigned-asset"
    service.get_asset_path.assert_not_awaited()


def test_download_document_falls_back_to_file_response_when_no_presigned_url(tmp_path: Path):
    file_path = tmp_path / "demo.pdf"
    file_path.write_bytes(b"%PDF")

    service = AsyncMock()
    service.get_download_url = AsyncMock(return_value=None)
    service.get_download_path = AsyncMock(return_value=(file_path, "demo.pdf"))

    client = _build_client(service)
    response = client.get("/api/v1/documents/11111111-1111-1111-1111-111111111111/download")

    assert response.status_code == 200
    assert response.content == b"%PDF"
