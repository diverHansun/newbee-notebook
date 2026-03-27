from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from newbee_notebook.api.dependencies import get_video_service
from newbee_notebook.api.routers import videos as videos_router
from newbee_notebook.application.services.video_service import VideoSummaryNotFoundError
from newbee_notebook.domain.entities.video_summary import VideoSummary


def _build_client(service: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(videos_router.router, prefix="/api/v1")

    async def _override():
        return service

    app.dependency_overrides[get_video_service] = _override
    return TestClient(app)


def _make_summary(summary_id: str = "summary-1") -> VideoSummary:
    return VideoSummary(
        summary_id=summary_id,
        notebook_id="nb-1",
        platform="bilibili",
        video_id="BV1xx411c7mD",
        source_url="https://www.bilibili.com/video/BV1xx411c7mD",
        title="Video title",
        cover_url="https://example.com/cover.jpg",
        duration_seconds=120,
        uploader_name="Uploader",
        uploader_id="12345",
        stats={"view": 42},
        summary_content="## Summary",
        status="completed",
        created_at=datetime(2026, 3, 27, 10, 0, 0),
        updated_at=datetime(2026, 3, 27, 10, 5, 0),
    )


def test_list_videos_returns_response():
    service = AsyncMock()
    service.list_by_notebook = AsyncMock(return_value=[_make_summary()])

    client = _build_client(service)
    response = client.get("/api/v1/videos", params={"notebook_id": "nb-1"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["summaries"][0]["summary_id"] == "summary-1"


def test_summarize_video_streams_sse_events():
    service = AsyncMock()

    async def _summarize(url_or_bvid: str, notebook_id: str | None = None, progress_callback=None):
        await progress_callback(
            "info",
            {"title": "Video title", "duration": 120, "author_name": "Uploader"},
        )
        await progress_callback("done", {"summary_id": "summary-1", "status": "completed"})
        return _make_summary()

    service.summarize = AsyncMock(side_effect=_summarize)

    client = _build_client(service)
    response = client.post(
        "/api/v1/videos/summarize",
        json={"url_or_bvid": "BV1xx411c7mD", "notebook_id": "nb-1"},
    )

    assert response.status_code == 200
    assert "event: info" in response.text
    assert "event: done" in response.text
    service.summarize.assert_awaited_once()


def test_get_video_returns_404_when_missing():
    service = AsyncMock()
    service.get = AsyncMock(side_effect=VideoSummaryNotFoundError("missing"))

    client = _build_client(service)
    response = client.get("/api/v1/videos/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Video summary not found"


def test_delete_video_returns_204():
    service = AsyncMock()
    service.delete = AsyncMock(return_value=True)

    client = _build_client(service)
    response = client.delete("/api/v1/videos/summary-1")

    assert response.status_code == 204
    service.delete.assert_awaited_once_with("summary-1")


def test_associate_and_disassociate_notebook_return_204():
    service = AsyncMock()
    service.associate_notebook = AsyncMock(return_value=_make_summary())
    service.disassociate_notebook = AsyncMock(return_value=_make_summary())

    client = _build_client(service)

    associate_response = client.post(
        "/api/v1/videos/summary-1/notebook",
        json={"notebook_id": "nb-1"},
    )
    disassociate_response = client.delete("/api/v1/videos/summary-1/notebook")

    assert associate_response.status_code == 204
    assert disassociate_response.status_code == 204
    service.associate_notebook.assert_awaited_once_with("summary-1", "nb-1")
    service.disassociate_notebook.assert_awaited_once_with("summary-1")


def test_video_info_proxy_returns_payload():
    service = AsyncMock()
    service.fetch_video_info = AsyncMock(
        return_value={
            "video_id": "BV1xx411c7mD",
            "source_url": "https://www.bilibili.com/video/BV1xx411c7mD",
            "title": "Video title",
            "cover_url": "https://example.com/cover.jpg",
            "duration_seconds": 120,
            "uploader_name": "Uploader",
            "uploader_id": "12345",
            "stats": {"view": 42},
        }
    )

    client = _build_client(service)
    response = client.get("/api/v1/videos/info", params={"url_or_bvid": "BV1xx411c7mD"})

    assert response.status_code == 200
    assert response.json()["video_id"] == "BV1xx411c7mD"
    service.fetch_video_info.assert_awaited_once_with("BV1xx411c7mD")
