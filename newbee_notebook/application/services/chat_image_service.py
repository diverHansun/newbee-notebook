"""Application service for user-uploaded chat images."""

from __future__ import annotations

import asyncio
import base64
import hashlib
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

from PIL import Image, UnidentifiedImageError

from newbee_notebook.domain.entities.base import generate_uuid
from newbee_notebook.domain.entities.chat_image import ChatImage
from newbee_notebook.domain.repositories.chat_image_repository import ChatImageRepository
from newbee_notebook.infrastructure.storage.base import StorageBackend


MAX_CHAT_IMAGE_COUNT = 10
MAX_CHAT_IMAGE_BYTES = 10 * 1024 * 1024
LLM_LONG_EDGE = 2048
THUMBNAIL_LONG_EDGE = 384


class ChatImageValidationError(ValueError):
    """Raised when an uploaded image fails validation."""


class ChatImageNotFoundError(ValueError):
    """Raised when an image record or stored object is missing."""


@dataclass(frozen=True)
class ChatImageFailure:
    filename: str
    reason: str


@dataclass(frozen=True)
class ChatImageUploadResult:
    images: list[ChatImage] = field(default_factory=list)
    failed: list[ChatImageFailure] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.images)


@dataclass(frozen=True)
class ChatImageContent:
    image: ChatImage
    data: bytes


def _sniff_image_type(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    raise ChatImageValidationError("Unsupported image type. Only PNG, JPEG, and WEBP are allowed.")


def _image_format_for_mime(mime_type: str) -> str:
    if mime_type == "image/jpeg":
        return "JPEG"
    if mime_type == "image/webp":
        return "WEBP"
    return "PNG"


def _read_image_size(data: bytes) -> tuple[int | None, int | None]:
    try:
        with Image.open(BytesIO(data)) as image:
            return image.size
    except (UnidentifiedImageError, OSError) as exc:
        raise ChatImageValidationError("Invalid image content.") from exc


def _resize_image(data: bytes, mime_type: str, *, long_edge: int) -> bytes:
    try:
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
            if max(width, height) <= long_edge:
                return data
            image.thumbnail((long_edge, long_edge))
            if mime_type == "image/jpeg":
                image = image.convert("RGB")
            buffer = BytesIO()
            image.save(buffer, format=_image_format_for_mime(mime_type))
            return buffer.getvalue()
    except (UnidentifiedImageError, OSError) as exc:
        raise ChatImageValidationError("Invalid image content.") from exc


class ChatImageService:
    """Validate, store, and load user-uploaded images for chat turns."""

    def __init__(
        self,
        *,
        chat_image_repo: ChatImageRepository,
        storage: StorageBackend,
    ):
        self._chat_image_repo = chat_image_repo
        self._storage = storage

    async def upload_images(
        self,
        *,
        session_id: str,
        files: list[Any],
    ) -> ChatImageUploadResult:
        if not files:
            raise ChatImageValidationError("At least one image file is required.")
        if len(files) > MAX_CHAT_IMAGE_COUNT:
            raise ChatImageValidationError(
                f"At most {MAX_CHAT_IMAGE_COUNT} images can be uploaded at once."
            )

        uploaded: list[ChatImage] = []
        failed: list[ChatImageFailure] = []
        for file in files:
            filename = str(getattr(file, "filename", "") or "image")
            try:
                uploaded.append(
                    await self._upload_one(session_id=session_id, file=file)
                )
            except ChatImageValidationError as exc:
                failed.append(ChatImageFailure(filename=filename, reason=str(exc)))

        if not uploaded and failed:
            raise ChatImageValidationError(failed[0].reason)
        return ChatImageUploadResult(images=uploaded, failed=failed)

    async def _upload_one(self, *, session_id: str, file: Any) -> ChatImage:
        read = getattr(file, "read", None)
        if not callable(read):
            raise ChatImageValidationError("Invalid upload file.")
        data = await read()
        if not data:
            raise ChatImageValidationError("Empty image file.")
        if len(data) > MAX_CHAT_IMAGE_BYTES:
            raise ChatImageValidationError(
                f"Image exceeds {MAX_CHAT_IMAGE_BYTES // (1024 * 1024)}MB limit."
            )

        mime_type, extension = _sniff_image_type(data)
        width, height = await asyncio.to_thread(_read_image_size, data)
        image_id = generate_uuid()
        storage_key = f"chat-images/{session_id}/{image_id}.{extension}"
        image = ChatImage(
            image_id=image_id,
            session_id=session_id,
            storage_key=storage_key,
            mime_type=mime_type,
            size_bytes=len(data),
            width=width,
            height=height,
            sha256=hashlib.sha256(data).hexdigest(),
        )
        await self._storage.save_file(storage_key, BytesIO(data), content_type=mime_type)
        return await self._chat_image_repo.create(image)

    async def assert_belongs_to_session(
        self,
        *,
        session_id: str,
        image_ids: list[str],
    ) -> None:
        requested = [str(image_id).strip() for image_id in image_ids if str(image_id).strip()]
        if not requested:
            return
        images = await self._chat_image_repo.list_by_ids(requested)
        by_id = {image.image_id: image for image in images if image.deleted_at is None}
        missing = [
            image_id
            for image_id in requested
            if image_id not in by_id or by_id[image_id].session_id != session_id
        ]
        if missing:
            raise ChatImageNotFoundError(
                f"Image not found in session: {', '.join(missing)}"
            )

    async def get_binary(self, image_id: str) -> ChatImageContent:
        image = await self._chat_image_repo.get(image_id)
        if image is None or image.deleted_at is not None:
            raise ChatImageNotFoundError(f"Chat image not found: {image_id}")
        try:
            data = await self._storage.get_file(image.storage_key)
        except FileNotFoundError as exc:
            raise ChatImageNotFoundError(
                f"Chat image binary not found for {image_id}: {image.storage_key}"
            ) from exc
        return ChatImageContent(image=image, data=data)

    async def get_thumbnail(self, image_id: str) -> ChatImageContent:
        content = await self.get_binary(image_id)
        data = await asyncio.to_thread(
            _resize_image,
            content.data,
            content.image.mime_type,
            long_edge=THUMBNAIL_LONG_EDGE,
        )
        return ChatImageContent(image=content.image, data=data)

    async def load_for_llm(self, image_id: str) -> dict[str, Any]:
        content = await self.get_binary(image_id)
        data = await asyncio.to_thread(
            _resize_image,
            content.data,
            content.image.mime_type,
            long_edge=LLM_LONG_EDGE,
        )
        encoded = base64.b64encode(data).decode("ascii")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{content.image.mime_type};base64,{encoded}"},
        }
