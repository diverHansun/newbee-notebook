from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from newbee_notebook.application.services.video_concurrency import (
    VideoConcurrencyController,
)
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
    repo = AsyncMock()
    repo.count_by_status.return_value = 0
    repo.commit = AsyncMock()
    return repo


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
def concurrency_controller():
    return VideoConcurrencyController(
        max_processing_videos=5,
        max_llm_concurrency=2,
        max_asr_concurrency=2,
    )


@pytest.fixture
def service(video_repo, bili_client, llm_client, storage, ref_repo, asr_pipeline, concurrency_controller):
    from newbee_notebook.application.services.video_service import VideoService

    return VideoService(
        video_repo=video_repo,
        bili_client=bili_client,
        llm_client=llm_client,
        storage=storage,
        ref_repo=ref_repo,
        asr_pipeline=asr_pipeline,
        concurrency_controller=concurrency_controller,
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
async def test_summarize_marks_summary_failed_when_subtitle_missing_and_asr_disabled(
    video_repo,
    bili_client,
    llm_client,
    storage,
    ref_repo,
):
    from newbee_notebook.application.services.video_service import (
        VideoService,
        VideoTranscriptUnavailableError,
    )

    video_repo.get_by_platform_and_video_id.return_value = None
    video_repo.create.side_effect = lambda summary: summary
    video_repo.update.side_effect = lambda summary: summary
    bili_client.get_video_subtitle.return_value = ("", [])
    events: list[tuple[str, dict]] = []

    async def progress(event: str, payload: dict) -> None:
        events.append((event, payload))

    service = VideoService(
        video_repo=video_repo,
        bili_client=bili_client,
        llm_client=llm_client,
        storage=storage,
        ref_repo=ref_repo,
        asr_pipeline=None,
    )

    with pytest.raises(VideoTranscriptUnavailableError):
        await service.summarize("BV1xx411c7mD", progress_callback=progress)

    failed_summary = video_repo.update.await_args_list[-1].args[0]
    assert failed_summary.status == "failed"
    assert "ASR is disabled" in failed_summary.error_message
    assert events[0][0] == "start"
    assert events[-1][0] == "error"
    llm_client.chat.assert_not_awaited()
    storage.save_file.assert_not_awaited()


@pytest.mark.anyio
async def test_summarize_retries_failed_summary_without_creating_a_new_row(
    service,
    video_repo,
):
    existing_failed = VideoSummary(
        summary_id="summary-failed",
        notebook_id="nb-old",
        platform="bilibili",
        video_id="BV1xx411c7mD",
        source_url="https://www.bilibili.com/video/BV1xx411c7mD",
        title="Old title",
        status="failed",
        error_message="previous raw error",
    )
    video_repo.get_by_platform_and_video_id.return_value = existing_failed
    update_snapshots: list[tuple[str, str | None]] = []

    def update_summary(summary):
        update_snapshots.append((summary.status, summary.error_message))
        return summary

    video_repo.update.side_effect = update_summary

    summary = await service.summarize("BV1xx411c7mD", notebook_id="nb-1")

    video_repo.create.assert_not_awaited()
    assert update_snapshots[0] == ("processing", None)
    assert summary.summary_id == "summary-failed"
    assert summary.status == "completed"


@pytest.mark.anyio
async def test_summarize_sanitizes_unexpected_errors_for_stream_and_storage(
    service,
    video_repo,
    llm_client,
):
    video_repo.get_by_platform_and_video_id.return_value = None
    video_repo.create.side_effect = lambda summary: summary
    video_repo.update.side_effect = lambda summary: summary
    llm_client.chat.side_effect = RuntimeError(
        "duplicate key value violates unique constraint uq_video_summaries_platform_video_id"
    )
    events: list[tuple[str, dict]] = []

    async def progress(event: str, payload: dict) -> None:
        events.append((event, payload))

    with pytest.raises(RuntimeError):
        await service.summarize("BV1xx411c7mD", progress_callback=progress)

    failed_summary = video_repo.update.await_args_list[-1].args[0]
    assert failed_summary.status == "failed"
    assert failed_summary.error_message == "Video summarization failed. Please retry."
    assert events[-1] == (
        "error",
        {
            "video_id": "BV1xx411c7mD",
            "error_code": "E_VIDEO_SUMMARIZE_FAILED",
            "message": "Video summarization failed. Please retry.",
        },
    )


@pytest.mark.anyio
async def test_get_video_ai_conclusion_proxies_to_client(service, bili_client):
    bili_client.get_video_ai_conclusion.return_value = "Quick AI summary"

    payload = await service.get_video_ai_conclusion("BV1xx411c7mD")

    assert payload == "Quick AI summary"
    bili_client.get_video_ai_conclusion.assert_awaited_once_with("BV1xx411c7mD")


@pytest.mark.anyio
async def test_summarize_uses_asr_fallback_when_subtitle_missing(
    service,
    video_repo,
    bili_client,
    asr_pipeline,
):
    video_repo.get_by_platform_and_video_id.return_value = None
    video_repo.create.side_effect = lambda summary: summary
    video_repo.update.side_effect = lambda summary: summary
    events: list[tuple[str, dict]] = []
    bili_client.get_video_subtitle.return_value = ("", [])

    async def progress(event: str, payload: dict) -> None:
        events.append((event, payload))

    summary = await service.summarize("BV1xx411c7mD", progress_callback=progress)

    assert summary.status == "completed"
    assert summary.transcript_source == "asr"
    asr_pipeline.transcribe.assert_awaited_once()
    assert [event for event, _payload in events] == ["start", "asr", "summarize", "done"]


@pytest.mark.anyio
async def test_summarize_emits_start_after_processing_summary_is_created(
    service,
    video_repo,
):
    video_repo.get_by_platform_and_video_id.return_value = None
    recorded_steps: list[str] = []

    def create_summary(summary):
        recorded_steps.append("create")
        return summary

    video_repo.create.side_effect = create_summary
    video_repo.update.side_effect = lambda summary: summary
    video_repo.commit.side_effect = lambda: recorded_steps.append("commit")

    async def progress(event: str, payload: dict) -> None:
        if event == "start":
            recorded_steps.append("start")

    await service.summarize("BV1xx411c7mD", progress_callback=progress)

    assert recorded_steps[:3] == ["create", "commit", "start"]


@pytest.mark.anyio
async def test_summarize_commits_completed_summary_before_done_event(
    service,
    video_repo,
):
    video_repo.get_by_platform_and_video_id.return_value = None
    recorded_steps: list[str] = []

    video_repo.create.side_effect = lambda summary: summary

    def update_summary(summary):
        recorded_steps.append(summary.status)
        return summary

    video_repo.update.side_effect = update_summary
    video_repo.commit.side_effect = lambda: recorded_steps.append("commit")

    async def progress(event: str, payload: dict) -> None:
        if event == "done":
            recorded_steps.append("done")

    await service.summarize("BV1xx411c7mD", progress_callback=progress)

    assert recorded_steps[-3:] == ["completed", "commit", "done"]


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
async def test_summarize_rejects_when_processing_capacity_is_full(service, video_repo):
    from newbee_notebook.application.services.video_service import (
        VideoConcurrentProcessingLimitError,
    )

    video_repo.get_by_platform_and_video_id.return_value = None
    video_repo.count_by_status.return_value = 5

    with pytest.raises(VideoConcurrentProcessingLimitError):
        await service.summarize("BV1xx411c7mD")

    video_repo.create.assert_not_awaited()
    video_repo.commit.assert_not_awaited()


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


@pytest.mark.anyio
async def test_fetch_video_info_supports_youtube(video_repo, bili_client, llm_client, storage, ref_repo):
    from newbee_notebook.application.services.video_service import VideoService

    youtube_client = SimpleNamespace(
        is_youtube_input=lambda value: "youtu" in value,
        extract_video_id=lambda _value: "dQw4w9WgXcQ",
        get_video_info=AsyncMock(
            return_value={
                "video_id": "dQw4w9WgXcQ",
                "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "title": "YouTube title",
                "cover_url": "https://example.com/yt-cover.jpg",
                "duration_seconds": 215,
                "uploader_name": "YT Channel",
                "uploader_id": "channel-1",
                "stats": {"view_count": 99},
            }
        ),
    )
    service = VideoService(
        video_repo=video_repo,
        bili_client=bili_client,
        youtube_client=youtube_client,
        llm_client=llm_client,
        storage=storage,
        ref_repo=ref_repo,
        asr_pipeline=None,
    )

    info = await service.fetch_video_info("https://youtu.be/dQw4w9WgXcQ")

    assert info["video_id"] == "dQw4w9WgXcQ"
    youtube_client.get_video_info.assert_awaited_once_with("dQw4w9WgXcQ")
    bili_client.get_video_info.assert_not_awaited()


@pytest.mark.anyio
async def test_llm_calls_wait_in_shared_two_slot_queue(
    video_repo,
    bili_client,
    storage,
    ref_repo,
    concurrency_controller,
):
    from newbee_notebook.application.services.video_service import VideoService

    active = 0
    peak = 0

    async def chat(*, messages):
        nonlocal active, peak
        assert messages
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.05)
        active -= 1
        return _llm_response("## Summary")

    llm_client = AsyncMock()
    llm_client.chat.side_effect = chat
    service = VideoService(
        video_repo=video_repo,
        bili_client=bili_client,
        llm_client=llm_client,
        storage=storage,
        ref_repo=ref_repo,
        asr_pipeline=None,
        concurrency_controller=concurrency_controller,
    )

    await asyncio.gather(
        service._generate_summary_content(info={"title": "v1"}, transcript_text="one", lang="zh"),
        service._generate_summary_content(info={"title": "v2"}, transcript_text="two", lang="zh"),
        service._generate_summary_content(info={"title": "v3"}, transcript_text="three", lang="zh"),
    )

    assert peak == 2
    assert llm_client.chat.await_count == 3


@pytest.mark.anyio
async def test_asr_calls_wait_in_shared_two_slot_queue(
    video_repo,
    bili_client,
    llm_client,
    storage,
    ref_repo,
    concurrency_controller,
):
    from newbee_notebook.application.services.video_service import VideoService

    active = 0
    peak = 0

    async def transcribe(payload):
        nonlocal active, peak
        assert payload["video_id"]
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.05)
        active -= 1
        return "asr transcript"

    asr_pipeline = AsyncMock()
    asr_pipeline.transcribe.side_effect = transcribe
    service = VideoService(
        video_repo=video_repo,
        bili_client=bili_client,
        llm_client=llm_client,
        storage=storage,
        ref_repo=ref_repo,
        asr_pipeline=asr_pipeline,
        concurrency_controller=concurrency_controller,
    )

    await asyncio.gather(
        service._transcribe_with_asr("youtube", "vid-1", {"source_url": "https://example.com/1"}),
        service._transcribe_with_asr("youtube", "vid-2", {"source_url": "https://example.com/2"}),
        service._transcribe_with_asr("youtube", "vid-3", {"source_url": "https://example.com/3"}),
    )

    assert peak == 2
    assert asr_pipeline.transcribe.await_count == 3


@pytest.mark.anyio
async def test_summarize_supports_youtube_with_transcript_chain(
    video_repo,
    bili_client,
    llm_client,
    storage,
    ref_repo,
):
    from newbee_notebook.application.services.video_service import VideoService

    video_repo.get_by_platform_and_video_id.return_value = None
    video_repo.create.side_effect = lambda summary: summary
    video_repo.update.side_effect = lambda summary: summary
    storage.save_file.return_value = "videos/transcripts/youtube-dQw4w9WgXcQ.txt"

    youtube_client = SimpleNamespace(
        is_youtube_input=lambda value: "youtu" in value,
        extract_video_id=lambda _value: "dQw4w9WgXcQ",
        get_video_info=AsyncMock(
            return_value={
                "video_id": "dQw4w9WgXcQ",
                "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "title": "YouTube title",
                "cover_url": "https://example.com/yt-cover.jpg",
                "duration_seconds": 215,
                "uploader_name": "YT Channel",
                "uploader_id": "channel-1",
                "stats": {"view_count": 99},
            }
        ),
        get_transcript=AsyncMock(return_value=("youtube transcript", "subtitle")),
    )
    events: list[tuple[str, dict]] = []

    async def progress(event: str, payload: dict) -> None:
        events.append((event, payload))

    service = VideoService(
        video_repo=video_repo,
        bili_client=bili_client,
        youtube_client=youtube_client,
        llm_client=llm_client,
        storage=storage,
        ref_repo=ref_repo,
        asr_pipeline=None,
    )

    summary = await service.summarize(
        "https://youtu.be/dQw4w9WgXcQ",
        notebook_id="nb-1",
        lang="en",
        progress_callback=progress,
    )

    assert summary.platform == "youtube"
    assert summary.video_id == "dQw4w9WgXcQ"
    assert summary.transcript_source == "subtitle"
    assert [event for event, _payload in events] == ["start", "info", "subtitle", "summarize", "done"]
