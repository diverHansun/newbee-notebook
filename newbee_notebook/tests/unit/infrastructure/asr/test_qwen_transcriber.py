from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_qwen_transcribe_segments_preserves_input_order(monkeypatch, tmp_path: Path):
    from newbee_notebook.infrastructure.asr.qwen_transcriber import QwenTranscriber

    transcriber = QwenTranscriber(api_key="token")
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
async def test_qwen_transcribe_one_posts_openai_compatible_payload(monkeypatch, tmp_path: Path):
    from newbee_notebook.infrastructure.asr.qwen_transcriber import QwenTranscriber

    segment = tmp_path / "seg.wav"
    segment.write_bytes(b"fake-audio")

    class FakeResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "hello transcript",
                        }
                    }
                ]
            }

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

        def post(self, url: str, *, json: dict, headers: dict[str, str]):
            assert url == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
            assert headers["Authorization"] == "Bearer token"
            assert json["model"] == "qwen3-asr-flash"
            assert json["messages"][0]["content"][0]["type"] == "input_audio"
            assert json["messages"][0]["content"][0]["input_audio"]["data"].startswith("data:audio/wav;base64,")
            assert json["asr_options"]["enable_itn"] is False
            return FakeResponse()

    monkeypatch.setattr("newbee_notebook.infrastructure.asr.qwen_transcriber.aiohttp.ClientSession", FakeSession)

    transcriber = QwenTranscriber(api_key="token")

    result = await transcriber._transcribe_one(str(segment), 0)

    assert result == "hello transcript"
