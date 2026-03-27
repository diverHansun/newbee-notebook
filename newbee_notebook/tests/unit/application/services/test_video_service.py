from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from newbee_notebook.domain.entities.video_summary import VideoSummary


def _llm_response(content: str):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
            )
        ]
    )


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def video_repo():
    return AsyncMock()


@pytest.fixture
def bili_client():
    client = AsyncMock()
    client.extract_bvid.return_value = "BV1xx411c7mD"
    client.get_video_info.return_value = {
        "video_id": "BV1xx411c7mD",
        "source_url": "https://www.bilibili.com/video/BV1xx411c7mD",
        "title": "Video title",
        "cover_url": "https://example.com/cover.jpg",
        "duration_seconds": 120,
        "uploader_name": "Uploader",
        "uploader_id": "12345",
        "stats": {"view": 42},
    }
    client.get_video_subtitle.return_value = ("subtitle text", [])
    return client


@pytest.fixture
def llm_client():
    client = AsyncMock()
    client.chat.return_value = _llm_response("## Summary")
    return client


@pytest.fixture
def storage():
    storage = AsyncMock()
    storage.save_file.return_value = "videos/transcripts/BV1xx411c7mD.txt"
    return storage


@pytest.fixture
def ref_repo():
    return AsyncMock()


@pytest.fixture
def asr_pipeline():
    pipeline = AsyncMock()
    pipeline.transcribe.return_value = "asr transcript"
    return pipeline


@pytest.fixture
def service(video_repo, bili_client, llm_client, storage, ref_repo, asr_pipeline):
    from newbee_notebook.application.services.video_service import VideoService

    return VideoService(
        video_repo=video_repo,
        bili_client=bili_client,
        llm_client=llm_client,
        storage=storage,
        ref_repo=ref_repo,
        asr_pipeline=asr_pipeline,
    )


@pytest.mark.anyio
async def test_summarize_reuses_completed_summary(service, video_repo):
    existing = VideoSummary(
        summary_id="summary-1",
        platform="bilibili",
        video_id="BV1xx411c7mD",
        title="Existing",
        status="completed",
    )
    video_repo.get_by_platform_and_video_id.return_value = existing
    events: list[tuple[str, dict]] = []

    async def progress(event: str, payload: dict) -> None:
        events.append((event, payload))

    summary = await service.summarize("BV1xx411c7mD", progress_callback=progress)

    assert summary is existing
    assert events == [("done", {"summary_id": "summary-1", "status": "completed", "reused": True})]


@pytest.mark.anyio
async def test_summarize_uses_asr_when_subtitle_missing(
    service,
    video_repo,
    bili_client,
    llm_client,
    storage,
    asr_pipeline,
):
    video_repo.get_by_platform_and_video_id.return_value = None
    video_repo.create.side_effect = lambda summary: summary
    video_repo.update.side_effect = lambda summary: summary
    bili_client.get_video_subtitle.return_value = ("", [])

    summary = await service.summarize("BV1xx411c7mD")

    assert summary.video_id == "BV1xx411c7mD"
    assert summary.transcript_source == "asr"
    assert summary.summary_content == "## Summary"
    assert summary.status == "completed"
    asr_pipeline.transcribe.assert_awaited_once()
    llm_client.chat.assert_awaited_once()
    storage.save_file.assert_awaited_once()


@pytest.mark.anyio
async def test_summarize_rejects_existing_processing_summary(service, video_repo):
    from newbee_notebook.application.services.video_service import (
        VideoSummarizingInProgressError,
    )

    video_repo.get_by_platform_and_video_id.return_value = VideoSummary(
        summary_id="summary-2",
        platform="bilibili",
        video_id="BV1xx411c7mD",
        title="Pending",
        status="processing",
    )

    with pytest.raises(VideoSummarizingInProgressError):
        await service.summarize("BV1xx411c7mD")


@pytest.mark.anyio
async def test_get_raises_when_summary_missing(service, video_repo):
    from newbee_notebook.application.services.video_service import VideoSummaryNotFoundError

    video_repo.get.return_value = None

    with pytest.raises(VideoSummaryNotFoundError):
        await service.get("missing")


@pytest.mark.anyio
async def test_delete_removes_summary_and_transcript(service, video_repo, storage):
    summary = VideoSummary(
        summary_id="summary-3",
        platform="bilibili",
        video_id="BV1xx411c7mD",
        title="Demo",
        status="completed",
        transcript_path="videos/transcripts/BV1xx411c7mD.txt",
    )
    video_repo.get.return_value = summary
    video_repo.delete.return_value = True

    deleted = await service.delete("summary-3")

    assert deleted is True
    storage.delete_file.assert_awaited_once_with("videos/transcripts/BV1xx411c7mD.txt")
    video_repo.delete.assert_awaited_once_with("summary-3")


@pytest.mark.anyio
async def test_associate_and_disassociate_notebook(service, video_repo):
    video_repo.update.side_effect = lambda summary: summary
    first_summary = VideoSummary(
        summary_id="summary-4",
        platform="bilibili",
        video_id="BV1xx411c7mD",
        title="Demo",
        status="completed",
    )
    second_summary = VideoSummary(
        summary_id="summary-4",
        notebook_id="nb-1",
        platform="bilibili",
        video_id="BV1xx411c7mD",
        title="Demo",
        status="completed",
    )
    video_repo.get.side_effect = [first_summary, second_summary]

    associated = await service.associate_notebook("summary-4", "nb-1")
    disassociated = await service.disassociate_notebook("summary-4")

    assert associated.notebook_id == "nb-1"
    assert disassociated.notebook_id is None
    assert video_repo.update.await_count == 2


@pytest.mark.anyio
async def test_add_and_remove_document_tag(service, video_repo, ref_repo):
    video_repo.update.side_effect = lambda summary: summary
    ref_repo.get_by_notebook_and_document.return_value = object()
    summary = VideoSummary(
        summary_id="summary-5",
        notebook_id="nb-1",
        platform="bilibili",
        video_id="BV1xx411c7mD",
        title="Demo",
        status="completed",
        document_ids=["doc-1"],
    )
    video_repo.get.return_value = summary

    updated = await service.add_document_tag("summary-5", "doc-2")
    updated = await service.remove_document_tag("summary-5", "doc-1")

    assert updated.document_ids == ["doc-2"]
    ref_repo.get_by_notebook_and_document.assert_awaited_once_with("nb-1", "doc-2")


@pytest.mark.anyio
async def test_video_query_helpers_delegate_to_bilibili_client(service, bili_client):
    bili_client.search_video.return_value = [{"video_id": "BV1xx411c7mD"}]
    bili_client.get_hot_videos.return_value = [{"video_id": "hot"}]
    bili_client.get_rank_videos.return_value = [{"video_id": "rank"}]
    bili_client.get_related_videos.return_value = [{"video_id": "related"}]

    info = await service.fetch_video_info("BV1xx411c7mD")
    results = await service.search_videos("python", page=2)
    hot = await service.get_hot_videos(page=3)
    rank = await service.get_rank_videos(day=7)
    related = await service.get_related_videos("BV1xx411c7mD")

    assert info["video_id"] == "BV1xx411c7mD"
    assert results == [{"video_id": "BV1xx411c7mD"}]
    assert hot == [{"video_id": "hot"}]
    assert rank == [{"video_id": "rank"}]
    assert related == [{"video_id": "related"}]
    bili_client.get_video_info.assert_awaited_once_with("BV1xx411c7mD")
    bili_client.search_video.assert_awaited_once_with("python", page=2)
    bili_client.get_hot_videos.assert_awaited_once_with(page=3)
    bili_client.get_rank_videos.assert_awaited_once_with(day=7)
    bili_client.get_related_videos.assert_awaited_once_with("BV1xx411c7mD")
