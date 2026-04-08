from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from newbee_notebook.api.dependencies import get_generated_image_service
from newbee_notebook.api.routers import generated_images as generated_images_router
from newbee_notebook.application.services.generated_image_service import (
    GeneratedImageContent,
)
from newbee_notebook.domain.entities.generated_image import GeneratedImage


def _sample_image(image_id: str = "img-1") -> GeneratedImage:
    return GeneratedImage(
        image_id=image_id,
        session_id="session-1",
        notebook_id="nb-1",
        message_id=101,
        tool_call_id="call-1",
        prompt="draw a bee",
        provider="qwen",
        model="qwen-image-2.0-pro",
        size="1024*1024",
        width=1024,
        height=1024,
        storage_key=f"generated-images/nb-1/session-1/{image_id}.png",
        file_size=1234,
        created_at=datetime(2026, 4, 8, 12, 0, 0),
        updated_at=datetime(2026, 4, 8, 12, 0, 0),
    )


def _build_client(service: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(generated_images_router.router, prefix="/api/v1")

    async def _override_service():
        return service

    app.dependency_overrides[get_generated_image_service] = _override_service
    return TestClient(app)


def test_get_generated_image_returns_metadata_payload():
    service = AsyncMock()
    service.get = AsyncMock(return_value=_sample_image("img-1"))
    client = _build_client(service)

    response = client.get("/api/v1/generated-images/img-1")

    assert response.status_code == 200
    body = response.json()
    assert body["image_id"] == "img-1"
    assert body["provider"] == "qwen"
    assert body["storage_key"].endswith("/img-1.png")


def test_get_generated_image_data_supports_etag_and_304_cache_validation():
    image = _sample_image("img-2")
    content = GeneratedImageContent(image=image, data=b"fake-image-binary")
    service = AsyncMock()
    service.get_binary = AsyncMock(return_value=content)
    client = _build_client(service)

    first = client.get("/api/v1/generated-images/img-2/data")
    assert first.status_code == 200
    assert first.headers["cache-control"] == "public, max-age=31536000, immutable"
    etag = first.headers["etag"]
    assert etag

    second = client.get(
        "/api/v1/generated-images/img-2/data",
        headers={"If-None-Match": etag},
    )
    assert second.status_code == 304


def test_get_generated_image_data_supports_download_mode():
    image = _sample_image("img-3")
    service = AsyncMock()
    service.get_binary = AsyncMock(
        return_value=GeneratedImageContent(image=image, data=b"fake-image-binary")
    )
    client = _build_client(service)

    response = client.get("/api/v1/generated-images/img-3/data?download=true")

    assert response.status_code == 200
    assert "attachment;" in response.headers["content-disposition"]
    assert "img-3.png" in response.headers["content-disposition"]


def test_list_session_generated_images_returns_all_items():
    service = AsyncMock()
    service.list_by_session = AsyncMock(return_value=[_sample_image("img-a"), _sample_image("img-b")])
    client = _build_client(service)

    response = client.get("/api/v1/sessions/session-1/generated-images")

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 2
    assert body["data"][0]["session_id"] == "session-1"

