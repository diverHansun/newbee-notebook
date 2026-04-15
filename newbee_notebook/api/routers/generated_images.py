"""Generated image metadata and content endpoints."""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query
from fastapi.responses import Response

from newbee_notebook.api.dependencies import get_generated_image_service
from newbee_notebook.api.models.responses import (
    GeneratedImageListResponse,
    GeneratedImageResponse,
)
from newbee_notebook.application.services.generated_image_service import (
    GeneratedImageNotFoundError,
    GeneratedImageService,
)
from newbee_notebook.domain.entities.generated_image import GeneratedImage

router = APIRouter()


def _to_response(image: GeneratedImage) -> GeneratedImageResponse:
    return GeneratedImageResponse(
        image_id=image.image_id,
        session_id=image.session_id,
        notebook_id=image.notebook_id,
        message_id=image.message_id,
        tool_call_id=image.tool_call_id,
        prompt=image.prompt,
        provider=image.provider,
        model=image.model,
        size=image.size,
        width=image.width,
        height=image.height,
        storage_key=image.storage_key,
        file_size=image.file_size,
        created_at=image.created_at,
        updated_at=image.updated_at,
    )


def _build_image_etag(data: bytes) -> str:
    return f"\"{hashlib.sha1(data).hexdigest()}\""


@router.get(
    "/generated-images/{image_id}",
    response_model=GeneratedImageResponse,
)
async def get_generated_image(
    image_id: str = Path(..., description="Generated image ID"),
    service: GeneratedImageService = Depends(get_generated_image_service),
):
    try:
        image = await service.get(image_id)
    except GeneratedImageNotFoundError:
        raise HTTPException(status_code=404, detail="Generated image not found")
    return _to_response(image)


@router.get(
    "/generated-images/{image_id}/data",
)
async def get_generated_image_data(
    image_id: str = Path(..., description="Generated image ID"),
    download: bool = Query(False, description="Set true to force attachment download"),
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    service: GeneratedImageService = Depends(get_generated_image_service),
):
    try:
        content = await service.get_binary(image_id)
    except GeneratedImageNotFoundError:
        raise HTTPException(status_code=404, detail="Generated image not found")

    etag = _build_image_etag(content.data)
    base_headers = {
        "Cache-Control": "public, max-age=31536000, immutable",
        "ETag": etag,
    }

    if if_none_match and etag in str(if_none_match):
        return Response(status_code=304, headers=base_headers)

    headers = dict(base_headers)
    if download:
        headers["Content-Disposition"] = (
            f'attachment; filename="{content.image.image_id}.png"'
        )

    return Response(
        content=content.data,
        media_type="image/png",
        headers=headers,
    )


@router.get(
    "/sessions/{session_id}/generated-images",
    response_model=GeneratedImageListResponse,
)
async def list_session_generated_images(
    session_id: str = Path(..., description="Session ID"),
    service: GeneratedImageService = Depends(get_generated_image_service),
):
    images = await service.list_by_session(session_id)
    return GeneratedImageListResponse(data=[_to_response(image) for image in images])

