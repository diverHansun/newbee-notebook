"""Routes for user-uploaded chat images."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from fastapi.responses import Response as BinaryResponse

from newbee_notebook.api.dependencies import get_chat_image_service, get_session_service
from newbee_notebook.api.models.chat_images import (
    ChatImageFailureResponse,
    ChatImageResponse,
    ChatImageUploadResponse,
)
from newbee_notebook.application.services.chat_image_service import (
    ChatImageNotFoundError,
    ChatImageService,
    ChatImageValidationError,
)
from newbee_notebook.application.services.session_service import (
    SessionNotFoundError,
    SessionService,
)
from newbee_notebook.domain.entities.chat_image import ChatImage


router = APIRouter(prefix="/chat")


def _image_response(image: ChatImage) -> ChatImageResponse:
    preview_url = f"/api/v1/chat/images/{image.image_id}/data"
    thumbnail_url = f"/api/v1/chat/images/{image.image_id}/thumbnail"
    return ChatImageResponse(
        image_id=image.image_id,
        session_id=image.session_id,
        storage_key=image.storage_key,
        mime_type=image.mime_type,
        size_bytes=image.size_bytes,
        width=image.width,
        height=image.height,
        sha256=image.sha256,
        preview_url=preview_url,
        thumbnail_url=thumbnail_url,
        created_at=image.created_at,
    )


async def _extract_upload_files(request: Request) -> list:
    form = await request.form()
    files = []
    for key in ("file", "files"):
        for item in form.getlist(key):
            if hasattr(item, "filename") and hasattr(item, "read"):
                files.append(item)
    return files


@router.post("/sessions/{session_id}/images", response_model=ChatImageUploadResponse)
async def upload_chat_images(
    request: Request,
    response: Response,
    session_id: str = Path(..., description="Session ID"),
    session_service: SessionService = Depends(get_session_service),
    chat_image_service: ChatImageService = Depends(get_chat_image_service),
):
    """Upload one or more user images for a chat session."""
    try:
        await session_service.get_or_raise(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    files = await _extract_upload_files(request)
    try:
        result = await chat_image_service.upload_images(
            session_id=session_id,
            files=files,
        )
    except ChatImageValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if result.failed and result.images:
        response.status_code = 207
    return ChatImageUploadResponse(
        images=[_image_response(image) for image in result.images],
        total=result.total,
        failed=[
            ChatImageFailureResponse(filename=item.filename, reason=item.reason)
            for item in result.failed
        ],
    )


@router.get("/images/{image_id}/data")
async def get_chat_image_data(
    image_id: str = Path(..., description="Uploaded chat image ID"),
    chat_image_service: ChatImageService = Depends(get_chat_image_service),
):
    """Return original uploaded chat image bytes."""
    try:
        content = await chat_image_service.get_binary(image_id)
    except ChatImageNotFoundError:
        raise HTTPException(status_code=404, detail="Chat image not found")
    return BinaryResponse(
        content=content.data,
        media_type=content.image.mime_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/images/{image_id}/thumbnail")
async def get_chat_image_thumbnail(
    image_id: str = Path(..., description="Uploaded chat image ID"),
    chat_image_service: ChatImageService = Depends(get_chat_image_service),
):
    """Return a thumbnail for an uploaded chat image."""
    try:
        content = await chat_image_service.get_thumbnail(image_id)
    except ChatImageNotFoundError:
        raise HTTPException(status_code=404, detail="Chat image not found")
    return BinaryResponse(
        content=content.data,
        media_type=content.image.mime_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )
