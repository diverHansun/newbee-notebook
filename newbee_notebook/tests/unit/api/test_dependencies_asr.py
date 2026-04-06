from __future__ import annotations

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_resolve_qwen_base_url_normalizes_api_prefix(monkeypatch):
    from newbee_notebook.api.dependencies import _resolve_qwen_base_url

    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://dashscope-intl.aliyuncs.com/api/v1")

    assert _resolve_qwen_base_url() == "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


@pytest.mark.anyio
async def test_get_asr_pipeline_dep_builds_qwen_pipeline(monkeypatch):
    from newbee_notebook.api import dependencies

    recorded: dict[str, object] = {}

    async def fake_get_asr_config_async(_session):
        return {
            "provider": "qwen",
            "model": "qwen3-asr-flash",
            "source": "db",
        }

    def fake_resolve_asr_api_key(provider: str):
        assert provider == "qwen"
        return "dashscope-token"

    def fake_build_audio_fetcher(_bili_client, _youtube_client):
        recorded["audio_fetcher"] = True

        async def _fetch(_source):
            return "audio.wav"

        return _fetch

    def fake_build_segmenter(max_segment_seconds: int):
        recorded["segment_seconds"] = max_segment_seconds

        def _segment(_audio_path: str):
            return ["seg.wav"]

        return _segment

    monkeypatch.setattr(dependencies, "get_asr_config_async", fake_get_asr_config_async)
    monkeypatch.setattr(dependencies, "resolve_asr_api_key", fake_resolve_asr_api_key)
    monkeypatch.setattr(dependencies, "_build_asr_audio_fetcher", fake_build_audio_fetcher)
    monkeypatch.setattr(dependencies, "_build_asr_segmenter", fake_build_segmenter)
    monkeypatch.setattr(
        dependencies,
        "_resolve_qwen_base_url",
        lambda: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )

    pipeline = await dependencies.get_asr_pipeline_dep(
        bili_client=object(),
        youtube_client=object(),
        session=object(),
    )

    assert pipeline is not None
    assert recorded["audio_fetcher"] is True
    assert recorded["segment_seconds"] == 180
    assert isinstance(pipeline._transcriber, dependencies.QwenTranscriber)
