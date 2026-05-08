from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from newbee_notebook.application.services.chat_image_service import (
    ChatImageNotFoundError,
    ChatImageService,
    ChatImageValidationError,
)


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\xf8\x0f\x00\x01\x01\x01\x00"
    b"\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _MemoryStorage:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    async def save_file(self, object_key: str, data, content_type: str = "application/octet-stream"):
        del content_type
        self.objects[object_key] = data.read()
        return object_key

    async def get_file(self, object_key: str) -> bytes:
        try:
            return self.objects[object_key]
        except KeyError as exc:
            raise FileNotFoundError(object_key) from exc

    async def delete_prefix(self, prefix: str) -> int:
        keys = [key for key in self.objects if key.startswith(prefix)]
        for key in keys:
            self.objects.pop(key, None)
        return len(keys)


def _upload_file(filename: str, data: bytes, content_type: str = "image/png"):
    return SimpleNamespace(
        filename=filename,
        content_type=content_type,
        read=AsyncMock(return_value=data),
    )


@pytest.mark.anyio
async def test_chat_image_service_uploads_valid_image_and_builds_data_url():
    repo = AsyncMock()
    storage = _MemoryStorage()
    service = ChatImageService(chat_image_repo=repo, storage=storage)

    async def _create(image):
        return image

    repo.create.side_effect = _create

    result = await service.upload_images(
        session_id="00000000-0000-0000-0000-000000000001",
        files=[_upload_file("one.png", PNG_1X1)],
    )

    assert result.total == 1
    assert result.images[0].mime_type == "image/png"
    assert result.images[0].storage_key.startswith(
        "chat-images/00000000-0000-0000-0000-000000000001/"
    )
    assert result.failed == []
    assert len(storage.objects) == 1

    repo.get.return_value = result.images[0]
    payload = await service.load_for_llm(result.images[0].image_id)

    assert payload["type"] == "image_url"
    assert payload["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.anyio
async def test_chat_image_service_rejects_non_image_magic_bytes():
    service = ChatImageService(chat_image_repo=AsyncMock(), storage=_MemoryStorage())

    with pytest.raises(ChatImageValidationError, match="Unsupported image type"):
        await service.upload_images(
            session_id="00000000-0000-0000-0000-000000000001",
            files=[_upload_file("fake.png", b"not really an image")],
        )


@pytest.mark.anyio
async def test_chat_image_service_asserts_session_ownership():
    repo = AsyncMock()
    repo.list_by_ids.return_value = []
    service = ChatImageService(chat_image_repo=repo, storage=_MemoryStorage())

    with pytest.raises(ChatImageNotFoundError):
        await service.assert_belongs_to_session(
            session_id="session-1",
            image_ids=["missing-image"],
        )
