"""Video API router."""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from fastapi.responses import StreamingResponse

from newbee_notebook.api.dependencies import get_video_service
from newbee_notebook.api.models.video_models import (
    AssociateNotebookRequest,
    SummarizeRequest,
    TagDocumentRequest,
    VideoInfoResponse,
    VideoListResponse,
    VideoSearchResponse,
    VideoSummaryListItemResponse,
    VideoSummaryListResponse,
    VideoSummaryResponse,
)
from newbee_notebook.application.services.video_service import (
    VideoService,
    VideoSummaryNotFoundError,
)


router = APIRouter()


def _format_sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _to_summary_response(summary) -> VideoSummaryResponse:
    return VideoSummaryResponse(
        summary_id=summary.summary_id,
        notebook_id=summary.notebook_id,
        platform=summary.platform,
        video_id=summary.video_id,
        source_url=summary.source_url,
        title=summary.title,
        cover_url=summary.cover_url,
        duration_seconds=summary.duration_seconds,
        uploader_name=summary.uploader_name,
        uploader_id=summary.uploader_id,
        summary_content=summary.summary_content,
        status=summary.status,
        error_message=summary.error_message,
        document_ids=list(summary.document_ids),
        stats=summary.stats,
        transcript_source=summary.transcript_source,
        transcript_path=summary.transcript_path,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
    )


def _to_summary_list_item(summary) -> VideoSummaryListItemResponse:
    return VideoSummaryListItemResponse(
        summary_id=summary.summary_id,
        notebook_id=summary.notebook_id,
        platform=summary.platform,
        video_id=summary.video_id,
        title=summary.title,
        cover_url=summary.cover_url,
        duration_seconds=summary.duration_seconds,
        uploader_name=summary.uploader_name,
        status=summary.status,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
    )


async def _summarize_stream(
    service: VideoService,
    request: SummarizeRequest,
) -> AsyncGenerator[str, None]:
    queue: asyncio.Queue[tuple[str | None, dict]] = asyncio.Queue()

    async def _progress_callback(event: str, payload: dict) -> None:
        await queue.put((event, payload))

    async def _run() -> None:
        try:
            await service.summarize(
                request.url_or_bvid,
                notebook_id=request.notebook_id,
                progress_callback=_progress_callback,
            )
        except Exception as exc:  # noqa: BLE001
            await queue.put(("error", {"message": str(exc)}))
        finally:
            await queue.put((None, {}))

    task = asyncio.create_task(_run())
    try:
        while True:
            event, payload = await queue.get()
            if event is None:
                break
            yield _format_sse(event, payload)
    finally:
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


@router.post("/videos/summarize")
async def summarize_video(
    request: SummarizeRequest,
    service: VideoService = Depends(get_video_service),
):
    return StreamingResponse(
        _summarize_stream(service, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/videos/info", response_model=VideoInfoResponse)
async def get_video_info(
    url_or_bvid: str = Query(..., min_length=1),
    service: VideoService = Depends(get_video_service),
):
    return VideoInfoResponse(**(await service.fetch_video_info(url_or_bvid)))


@router.get("/videos/search", response_model=VideoSearchResponse)
async def search_videos(
    keyword: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    service: VideoService = Depends(get_video_service),
):
    results = await service.search_videos(keyword, page=page)
    return VideoSearchResponse(results=results, total=len(results))


@router.get("/videos/hot", response_model=VideoListResponse)
async def get_hot_videos(
    page: int = Query(1, ge=1),
    service: VideoService = Depends(get_video_service),
):
    results = await service.get_hot_videos(page=page)
    return VideoListResponse(results=results, total=len(results))


@router.get("/videos/rank", response_model=VideoListResponse)
async def get_rank_videos(
    day: int = Query(3, ge=1),
    service: VideoService = Depends(get_video_service),
):
    results = await service.get_rank_videos(day=day)
    return VideoListResponse(results=results, total=len(results))


@router.get("/videos", response_model=VideoSummaryListResponse)
async def list_videos(
    notebook_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    service: VideoService = Depends(get_video_service),
):
    if notebook_id:
        summaries = await service.list_by_notebook(notebook_id, status=status)
    else:
        summaries = await service.list_all(status=status)
    return VideoSummaryListResponse(
        summaries=[_to_summary_list_item(summary) for summary in summaries],
        total=len(summaries),
    )


@router.get("/videos/{summary_id}", response_model=VideoSummaryResponse)
async def get_video_summary(
    summary_id: str = Path(..., min_length=1),
    service: VideoService = Depends(get_video_service),
):
    try:
        return _to_summary_response(await service.get(summary_id))
    except VideoSummaryNotFoundError:
        raise HTTPException(status_code=404, detail="Video summary not found")


@router.delete("/videos/{summary_id}", status_code=204)
async def delete_video_summary(
    summary_id: str = Path(..., min_length=1),
    service: VideoService = Depends(get_video_service),
):
    try:
        await service.delete(summary_id)
    except VideoSummaryNotFoundError:
        raise HTTPException(status_code=404, detail="Video summary not found")
    return Response(status_code=204)


@router.post("/videos/{summary_id}/notebook", status_code=204)
async def associate_video_notebook(
    request: AssociateNotebookRequest,
    summary_id: str = Path(..., min_length=1),
    service: VideoService = Depends(get_video_service),
):
    try:
        await service.associate_notebook(summary_id, request.notebook_id)
    except VideoSummaryNotFoundError:
        raise HTTPException(status_code=404, detail="Video summary not found")
    return Response(status_code=204)


@router.delete("/videos/{summary_id}/notebook", status_code=204)
async def disassociate_video_notebook(
    summary_id: str = Path(..., min_length=1),
    service: VideoService = Depends(get_video_service),
):
    try:
        await service.disassociate_notebook(summary_id)
    except VideoSummaryNotFoundError:
        raise HTTPException(status_code=404, detail="Video summary not found")
    return Response(status_code=204)


@router.post("/videos/{summary_id}/documents", status_code=204)
async def add_video_document(
    request: TagDocumentRequest,
    summary_id: str = Path(..., min_length=1),
    service: VideoService = Depends(get_video_service),
):
    try:
        await service.add_document_tag(summary_id, request.document_id)
    except VideoSummaryNotFoundError:
        raise HTTPException(status_code=404, detail="Video summary not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return Response(status_code=204)


@router.delete("/videos/{summary_id}/documents/{document_id}", status_code=204)
async def remove_video_document(
    summary_id: str = Path(..., min_length=1),
    document_id: str = Path(..., min_length=1),
    service: VideoService = Depends(get_video_service),
):
    try:
        await service.remove_document_tag(summary_id, document_id)
    except VideoSummaryNotFoundError:
        raise HTTPException(status_code=404, detail="Video summary not found")
    return Response(status_code=204)
