from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_zhipu_transcribe_segments_preserves_input_order(monkeypatch, tmp_path: Path):
    from newbee_notebook.infrastructure.asr.zhipu_transcriber import ZhipuTranscriber

    transcriber = ZhipuTranscriber(api_key="token")
    first = tmp_path / "seg-1.wav"
    second = tmp_path / "seg-2.wav"
    first.write_bytes(b"a")
    second.write_bytes(b"b")

    async def fake_transcribe_one(path: str, index: int) -> str:
        await asyncio.sleep(0.02 if index == 0 else 0.0)
        return f"{Path(path).stem}:{index}"

    monkeypatch.setattr(transcriber, "_transcribe_one", fake_transcribe_one)

    result = await transcriber.transcribe_segments([str(first), str(second)])

    assert result == "seg-1:0 seg-2:1"


@pytest.mark.anyio
async def test_zhipu_transcribe_one_posts_multipart_and_parses_text(monkeypatch, tmp_path: Path):
    from newbee_notebook.infrastructure.asr.zhipu_transcriber import ZhipuTranscriber

    segment = tmp_path / "seg.wav"
    segment.write_bytes(b"fake-audio")

    class FakeResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def json(self):
            return {"text": "hello transcript"}

        async def text(self):
            return "hello transcript"

    class FakeSession:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def post(self, url: str, *, data, headers: dict[str, str]):
            assert url == "https://open.bigmodel.cn/api/paas/v4/audio/transcriptions"
            assert headers["Authorization"] == "Bearer token"
            assert data is not None
            return FakeResponse()

    monkeypatch.setattr("newbee_notebook.infrastructure.asr.zhipu_transcriber.aiohttp.ClientSession", FakeSession)

    transcriber = ZhipuTranscriber(api_key="token")

    result = await transcriber._transcribe_one(str(segment), 0)

    assert result == "hello transcript"
