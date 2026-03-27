"""Bilibili authentication API router."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse

from newbee_notebook.api.dependencies import get_bilibili_auth_manager
from newbee_notebook.api.models.video_models import AuthStatusResponse
from newbee_notebook.infrastructure.bilibili.auth import BilibiliAuthManager


router = APIRouter()


def _format_sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/bilibili/auth/status", response_model=AuthStatusResponse)
async def auth_status(
    manager: BilibiliAuthManager = Depends(get_bilibili_auth_manager),
):
    return AuthStatusResponse(logged_in=manager.load_credential() is not None)


@router.get("/bilibili/auth/qr")
async def qr_login(
    manager: BilibiliAuthManager = Depends(get_bilibili_auth_manager),
):
    async def _stream():
        async for event, payload in manager.stream_qr_login():
            yield _format_sse(event, payload)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/bilibili/auth/logout", status_code=204)
async def logout(
    manager: BilibiliAuthManager = Depends(get_bilibili_auth_manager),
):
    manager.clear_credential()
    return Response(status_code=204)
