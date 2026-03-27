from __future__ import annotations

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
