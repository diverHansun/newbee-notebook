from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from newbee_notebook.api.dependencies import get_chat_image_service, get_session_service
from newbee_notebook.api.routers import chat_images
from newbee_notebook.application.services.chat_image_service import ChatImageService


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\xf8\x0f\x00\x01\x01\x01\x00"
    b"\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
)


class _MemoryRepo:
    def __init__(self):
        self.images = {}

    async def create(self, image):
        self.images[image.image_id] = image
        return image

    async def get(self, image_id: str):
        return self.images.get(image_id)

    async def list_by_ids(self, image_ids: list[str]):
        return [self.images[image_id] for image_id in image_ids if image_id in self.images]

    async def list_by_session(self, session_id: str):
        return [image for image in self.images.values() if image.session_id == session_id]

    async def soft_delete_by_session(self, session_id: str):
        del session_id
        return 0


class _MemoryStorage:
    def __init__(self):
        self.objects = {}

    async def save_file(self, object_key: str, data, content_type: str = "application/octet-stream"):
        del content_type
        self.objects[object_key] = data.read()
        return object_key

    async def get_file(self, object_key: str):
        return self.objects[object_key]


class _FakeSessionService:
    async def get_or_raise(self, session_id: str):
        return object()


def _build_client():
    app = FastAPI()
    app.include_router(chat_images.router, prefix="/api/v1")
    service = ChatImageService(
        chat_image_repo=_MemoryRepo(),
        storage=_MemoryStorage(),
    )
    app.dependency_overrides[get_chat_image_service] = lambda: service
    app.dependency_overrides[get_session_service] = lambda: _FakeSessionService()
    return TestClient(app)


def test_upload_single_chat_image_and_read_original_data():
    client = _build_client()

    upload_response = client.post(
        "/api/v1/chat/sessions/session-1/images",
        files={"file": ("one.png", PNG_1X1, "image/png")},
    )

    assert upload_response.status_code == 200
    body = upload_response.json()
    assert body["total"] == 1
    assert body["failed"] == []
    image = body["images"][0]
    assert image["mime_type"] == "image/png"
    assert image["preview_url"].endswith(f"/chat/images/{image['image_id']}/data")
    assert image["thumbnail_url"].endswith(f"/chat/images/{image['image_id']}/thumbnail")

    data_response = client.get(f"/api/v1/chat/images/{image['image_id']}/data")

    assert data_response.status_code == 200
    assert data_response.headers["content-type"] == "image/png"
    assert data_response.content == PNG_1X1


def test_upload_chat_image_rejects_non_image_content():
    client = _build_client()

    response = client.post(
        "/api/v1/chat/sessions/session-1/images",
        files={"file": ("fake.png", b"not-image", "image/png")},
    )

    assert response.status_code == 400
    assert "Unsupported image type" in response.json()["detail"]
