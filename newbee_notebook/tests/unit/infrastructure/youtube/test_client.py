from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_get_video_info_falls_back_to_watch_page(monkeypatch):
    from newbee_notebook.infrastructure.youtube.client import YouTubeClient
    from newbee_notebook.infrastructure.youtube.exceptions import YouTubeNetworkError

    client = YouTubeClient()
    watch_page_info = {
        "video_id": "dQw4w9WgXcQ",
        "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "title": "Watch Page Title",
        "description": "desc",
        "cover_url": "https://example.com/cover.jpg",
        "duration_seconds": 215,
        "uploader_name": "Channel",
        "uploader_id": "channel-1",
        "stats": {"view_count": 99},
    }

    monkeypatch.setattr(client, "_extract_info", AsyncMock(side_effect=YouTubeNetworkError("yt-dlp unavailable")))
    monkeypatch.setattr(client, "_get_video_info_from_watch_page", AsyncMock(return_value=watch_page_info))

    info = await client.get_video_info("dQw4w9WgXcQ")

    assert info == watch_page_info


@pytest.mark.anyio
async def test_download_audio_falls_back_to_watch_page_stream(monkeypatch):
    from newbee_notebook.infrastructure.youtube.client import YouTubeClient

    client = YouTubeClient()
    html = (
        "<script>var ytInitialPlayerResponse = "
        '{"streamingData":{"adaptiveFormats":[{"mimeType":"audio/mp4; codecs=\\"mp4a.40.2\\"",'
        '"bitrate":128000,"url":"https://media.example/audio.m4a"}]}}</script>'
    )

    monkeypatch.setattr(client, "_download_audio_sync", lambda _video_id: (_ for _ in ()).throw(RuntimeError("yt-dlp missing")))
    monkeypatch.setattr(client, "_fetch_text", AsyncMock(return_value=html))
    download_binary = AsyncMock(return_value="C:/tmp/video-asr-/audio.m4a")
    monkeypatch.setattr(client, "_download_binary_to_workspace", download_binary)

    path = await client.download_audio("dQw4w9WgXcQ")

    assert path == "C:/tmp/video-asr-/audio.m4a"
    download_binary.assert_awaited_once_with(
        "dQw4w9WgXcQ",
        "https://media.example/audio.m4a",
        mime_type='audio/mp4; codecs="mp4a.40.2"',
    )


@pytest.mark.anyio
async def test_download_audio_uses_youtubei_after_watch_page_fallback_fails(monkeypatch):
    from newbee_notebook.infrastructure.youtube.client import YouTubeClient
    from newbee_notebook.infrastructure.youtube.exceptions import YouTubeNetworkError

    client = YouTubeClient()

    monkeypatch.setattr(client, "_download_audio_sync", lambda _video_id: (_ for _ in ()).throw(RuntimeError("yt-dlp missing")))
    monkeypatch.setattr(client, "_download_audio_from_watch_page", AsyncMock(side_effect=YouTubeNetworkError("no watch audio")))
    youtubei_fallback = AsyncMock(return_value="C:/tmp/video-asr-/audio.webm")
    monkeypatch.setattr(client, "_download_audio_from_youtubei", youtubei_fallback)

    path = await client.download_audio("dQw4w9WgXcQ")

    assert path == "C:/tmp/video-asr-/audio.webm"
    youtubei_fallback.assert_awaited_once_with("dQw4w9WgXcQ")