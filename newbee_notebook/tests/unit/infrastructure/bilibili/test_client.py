from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from bilibili_api.exceptions import ResponseCodeException

from newbee_notebook.infrastructure.bilibili.exceptions import InvalidBvidError, NotFoundError


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_extract_bvid_accepts_bilibili_url():
    from newbee_notebook.infrastructure.bilibili.client import extract_bvid

    assert extract_bvid("https://www.bilibili.com/video/BV1xx411c7mD") == "BV1xx411c7mD"


def test_extract_bvid_rejects_invalid_value():
    from newbee_notebook.infrastructure.bilibili.client import extract_bvid

    with pytest.raises(InvalidBvidError):
        extract_bvid("https://example.com/video/not-bvid")


def test_has_credentials_returns_false_when_credential_missing():
    from newbee_notebook.infrastructure.bilibili.client import BilibiliClient

    client = BilibiliClient(credential=None)

    assert client.has_credentials() is False


def test_has_credentials_returns_false_when_sessdata_empty():
    from newbee_notebook.infrastructure.bilibili.client import BilibiliClient

    client = BilibiliClient(credential=SimpleNamespace(sessdata=""))

    assert client.has_credentials() is False


def test_has_credentials_returns_true_when_sessdata_present():
    from newbee_notebook.infrastructure.bilibili.client import BilibiliClient

    client = BilibiliClient(credential=SimpleNamespace(sessdata="sess-token"))

    assert client.has_credentials() is True


@pytest.mark.anyio
async def test_get_video_info_normalizes_sdk_payload():
    from newbee_notebook.infrastructure.bilibili.client import BilibiliClient

    class FakeVideo:
        def __init__(self, *, bvid: str, credential=None):
            self.bvid = bvid
            self.credential = credential

        async def get_info(self):
            return {
                "bvid": self.bvid,
                "title": "Demo",
                "pic": "https://example.com/cover.jpg",
                "duration": 95,
                "owner": {"mid": 42, "name": "UP"},
                "stat": {"view": 12},
            }

    client = BilibiliClient(video_factory=FakeVideo)

    payload = await client.get_video_info("BV1xx411c7mD")

    assert payload["video_id"] == "BV1xx411c7mD"
    assert payload["uploader_name"] == "UP"
    assert payload["stats"]["view"] == 12


@pytest.mark.anyio
async def test_get_video_info_maps_not_found_error():
    from newbee_notebook.infrastructure.bilibili.client import BilibiliClient

    class FakeVideo:
        def __init__(self, *, bvid: str, credential=None):
            self.bvid = bvid
            self.credential = credential

        async def get_info(self):
            raise ResponseCodeException(-404, "not found")

    client = BilibiliClient(video_factory=FakeVideo)

    with pytest.raises(NotFoundError):
        await client.get_video_info("BV1xx411c7mD")


@pytest.mark.anyio
async def test_get_video_subtitle_prefers_chinese_track_and_flattens_text():
    from newbee_notebook.infrastructure.bilibili.client import BilibiliClient

    class FakeVideo:
        def __init__(self, *, bvid: str, credential=None):
            self.bvid = bvid
            self.credential = credential

        async def get_pages(self):
            return [{"cid": 1001}]

        async def get_player_info(self, *, cid: int):
            assert cid == 1001
            return {
                "subtitle": {
                    "subtitles": [
                        {"lan": "en", "subtitle_url": "//example.com/en.json"},
                        {"lan": "zh-CN", "subtitle_url": "//example.com/zh.json"},
                    ]
                }
            }

    async def fake_fetch_json(url: str):
        assert url == "https://example.com/zh.json"
        return {
            "body": [
                {"from": 0.0, "to": 1.0, "content": "hello"},
                {"from": 1.0, "to": 2.0, "content": "world"},
            ]
        }

    client = BilibiliClient(video_factory=FakeVideo, json_fetcher=fake_fetch_json)

    text, items = await client.get_video_subtitle("BV1xx411c7mD")

    assert text == "hello\nworld"
    assert items == [
        {"from": 0.0, "to": 1.0, "content": "hello"},
        {"from": 1.0, "to": 2.0, "content": "world"},
    ]


@pytest.mark.anyio
async def test_search_video_normalizes_results(monkeypatch):
    from newbee_notebook.infrastructure.bilibili import client as client_module

    search_by_type = AsyncMock(
        return_value={
            "result": [
                {
                    "bvid": "BV1xx411c7mD",
                    "title": "<em class=\"keyword\">Demo</em> Video",
                    "arcurl": "https://www.bilibili.com/video/BV1xx411c7mD",
                    "author": "UP",
                    "duration": "01:05",
                    "play": "1200",
                    "description": "<em>demo</em> description",
                }
            ]
        }
    )
    monkeypatch.setattr(
        client_module,
        "search",
        SimpleNamespace(
            search_by_type=search_by_type,
            SearchObjectType=SimpleNamespace(VIDEO="video"),
        ),
        raising=False,
    )

    client = client_module.BilibiliClient()

    payload = await client.search_video("demo", page=2)

    assert payload == [
        {
            "video_id": "BV1xx411c7mD",
            "title": "Demo Video",
            "url": "https://www.bilibili.com/video/BV1xx411c7mD",
            "author": "UP",
            "duration": 65,
            "play_count": 1200,
            "description": "demo description",
        }
    ]
    search_by_type.assert_awaited_once_with("demo", search_type="video", page=2)


@pytest.mark.anyio
async def test_get_hot_videos_normalizes_sdk_payload(monkeypatch):
    from newbee_notebook.infrastructure.bilibili import client as client_module

    get_hot_videos = AsyncMock(
        return_value={
            "list": [
                {
                    "bvid": "BV1xx411c7mD",
                    "title": "Hot Demo",
                    "pic": "https://example.com/hot.jpg",
                    "duration": 95,
                    "owner": {"mid": 42, "name": "Hot UP"},
                    "stat": {"view": 12},
                }
            ]
        }
    )
    monkeypatch.setattr(
        client_module,
        "hot",
        SimpleNamespace(get_hot_videos=get_hot_videos),
        raising=False,
    )

    client = client_module.BilibiliClient()

    payload = await client.get_hot_videos(page=3)

    assert payload[0]["video_id"] == "BV1xx411c7mD"
    assert payload[0]["title"] == "Hot Demo"
    assert payload[0]["uploader_name"] == "Hot UP"
    get_hot_videos.assert_awaited_once_with(pn=3, ps=20)


@pytest.mark.anyio
async def test_get_rank_videos_uses_requested_rank_window(monkeypatch):
    from newbee_notebook.infrastructure.bilibili import client as client_module

    get_rank = AsyncMock(
        return_value={
            "list": [
                {
                    "bvid": "BV1xx411c7mD",
                    "title": "Rank Demo",
                    "pic": "https://example.com/rank.jpg",
                    "duration": 95,
                    "owner": {"mid": 42, "name": "Rank UP"},
                    "stat": {"view": 12},
                }
            ]
        }
    )
    monkeypatch.setattr(
        client_module,
        "rank",
        SimpleNamespace(
            get_rank=get_rank,
            RankDayType=SimpleNamespace(THREE_DAY="three-day", WEEK="week"),
        ),
        raising=False,
    )

    client = client_module.BilibiliClient()

    payload = await client.get_rank_videos(day=7)

    assert payload[0]["title"] == "Rank Demo"
    get_rank.assert_awaited_once_with(day="week")


@pytest.mark.anyio
async def test_get_related_videos_normalizes_results():
    from newbee_notebook.infrastructure.bilibili.client import BilibiliClient

    class FakeVideo:
        def __init__(self, *, bvid: str, credential=None):
            self.bvid = bvid
            self.credential = credential

        async def get_related(self):
            return [
                {
                    "bvid": "BV1xx411c7mD",
                    "title": "Related Demo",
                    "pic": "https://example.com/related.jpg",
                    "duration": 95,
                    "owner": {"mid": 42, "name": "Related UP"},
                    "stat": {"view": 12},
                }
            ]

    client = BilibiliClient(video_factory=FakeVideo)

    payload = await client.get_related_videos("BV1xx411c7mD")

    assert payload[0]["video_id"] == "BV1xx411c7mD"
    assert payload[0]["title"] == "Related Demo"


@pytest.mark.anyio
async def test_get_video_ai_conclusion_extracts_summary_text():
    from newbee_notebook.infrastructure.bilibili.client import BilibiliClient

    class FakeVideo:
        def __init__(self, *, bvid: str, credential=None):
            self.bvid = bvid
            self.credential = credential

        async def get_pages(self):
            return [{"cid": 1001}]

        async def get_ai_conclusion(self, *, cid: int):
            assert cid == 1001
            return {"model_result": {"summary": "Quick AI summary"}}

    client = BilibiliClient(video_factory=FakeVideo)

    payload = await client.get_video_ai_conclusion("BV1xx411c7mD")

    assert payload == "Quick AI summary"


@pytest.mark.anyio
async def test_get_audio_url_prefers_dash_audio_stream(monkeypatch):
    from newbee_notebook.infrastructure.bilibili import client as client_module

    class FakeVideo:
        def __init__(self, *, bvid: str, credential=None):
            self.bvid = bvid
            self.credential = credential

        async def get_download_url(self, page_index: int = 0):
            assert page_index == 0
            return {"kind": "download"}

    class FakeDetecter:
        def __init__(self, data):
            assert data == {"kind": "download"}

        def detect_best_streams(self, **kwargs):
            return [
                SimpleNamespace(url="https://example.com/video.m4s"),
                SimpleNamespace(url="https://example.com/audio.m4s"),
            ]

    monkeypatch.setattr(
        client_module,
        "VideoDownloadURLDataDetecter",
        FakeDetecter,
        raising=False,
    )
    monkeypatch.setattr(
        client_module,
        "AudioQuality",
        SimpleNamespace(_64K="64k"),
        raising=False,
    )

    client = client_module.BilibiliClient(video_factory=FakeVideo)

    payload = await client.get_audio_url("BV1xx411c7mD")

    assert payload == "https://example.com/audio.m4s"


@pytest.mark.anyio
async def test_download_audio_writes_response_bytes(tmp_path, monkeypatch):
    from newbee_notebook.infrastructure.bilibili import client as client_module

    target = tmp_path / "audio.m4s"

    class FakeResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def raise_for_status(self):
            return None

        @property
        def content(self):
            return SimpleNamespace(iter_chunked=self._iter_chunked)

        async def _iter_chunked(self, _size: int):
            yield b"abc"
            yield b"123"

    class FakeSession:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def get(self, url: str, *, headers: dict[str, str]):
            assert url == "https://example.com/audio.m4s"
            assert headers["Referer"] == "https://www.bilibili.com"
            return FakeResponse()

    monkeypatch.setattr(client_module.aiohttp, "ClientSession", FakeSession)

    client = client_module.BilibiliClient()

    written = await client.download_audio("https://example.com/audio.m4s", str(target))

    assert written == 6
    assert target.read_bytes() == b"abc123"
