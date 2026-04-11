from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
import requests

from newbee_notebook.core.tools.image_generation import (
    DEFAULT_QWEN_IMAGE_API_URL,
    ImageAPIResult,
    ImageToolContext,
    _resolve_qwen_url,
    build_image_generation_tool,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_qwen_image_url_defaults_to_beijing_domain(monkeypatch):
    monkeypatch.delenv("QWEN_IMAGE_API_BASE", raising=False)
    monkeypatch.delenv("DASHSCOPE_IMAGE_API_BASE", raising=False)
    assert _resolve_qwen_url() == DEFAULT_QWEN_IMAGE_API_URL
    assert _resolve_qwen_url().startswith("https://dashscope.aliyuncs.com/")


def test_qwen_image_url_accepts_api_v1_base_and_normalizes(monkeypatch):
    monkeypatch.setenv("QWEN_IMAGE_API_BASE", "https://dashscope.aliyuncs.com/api/v1")
    assert (
        _resolve_qwen_url()
        == "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    )


@pytest.mark.anyio
async def test_image_generate_tool_persists_image_and_returns_structured_result(monkeypatch):
    monkeypatch.setattr(
        "newbee_notebook.core.tools.image_generation.generate_uuid",
        lambda: "img-1",
    )

    async def _fake_qwen_generate_image(**kwargs):
        assert kwargs["prompt"] == "a cute bee"
        return ImageAPIResult(
            image_urls=["https://example.com/generated.png"],
            model="qwen-image-2.0-pro",
            width=1024,
            height=1024,
        )

    async def _fake_download_image_bytes(url: str):
        assert url == "https://example.com/generated.png"
        return b"fake-png-binary"

    monkeypatch.setattr(
        "newbee_notebook.core.tools.image_generation.qwen_generate_image",
        _fake_qwen_generate_image,
    )
    monkeypatch.setattr(
        "newbee_notebook.core.tools.image_generation._download_image_bytes",
        _fake_download_image_bytes,
    )

    storage = AsyncMock()
    storage.save_file = AsyncMock(return_value="generated-images/nb-1/s-1/img-1.png")
    save_record = AsyncMock(return_value=None)

    tool = build_image_generation_tool(
        ImageToolContext(
            session_id="s-1",
            notebook_id="nb-1",
            provider="qwen",
            api_key="sk-test",
            storage=storage,
            save_record=save_record,
        )
    )

    result = await tool.execute(
        {
            "prompt": "a cute bee",
            "size": "1024x1024",
            "tool_call_id": "call-1",
        }
    )

    assert result.error is None
    assert len(result.images) == 1
    assert result.images[0].image_id == "img-1"
    assert result.images[0].provider == "qwen"
    assert result.metadata["provider"] == "qwen"
    storage.save_file.assert_awaited_once()
    save_record.assert_awaited_once()
    assert save_record.await_args.kwargs["tool_call_id"] == "call-1"
    assert save_record.await_args.kwargs["storage_key"].endswith("/img-1.png")


@pytest.mark.anyio
async def test_image_generate_tool_requires_prompt():
    storage = AsyncMock()
    save_record = AsyncMock(return_value=None)
    tool = build_image_generation_tool(
        ImageToolContext(
            session_id="s-1",
            notebook_id="nb-1",
            provider="qwen",
            api_key="sk-test",
            storage=storage,
            save_record=save_record,
        )
    )

    result = await tool.execute({})

    assert result.error == "prompt is required"
    storage.save_file.assert_not_called()
    save_record.assert_not_called()


@pytest.mark.anyio
async def test_image_generate_tool_accepts_width_and_height_and_persists_normalized_size(
    monkeypatch,
):
    monkeypatch.setattr(
        "newbee_notebook.core.tools.image_generation.generate_uuid",
        lambda: "img-2",
    )

    captured: dict[str, object] = {}

    async def _fake_qwen_generate_image(**kwargs):
        captured.update(kwargs)
        return ImageAPIResult(
            image_urls=["https://example.com/generated-2.png"],
            model="qwen-image-2.0-pro",
            width=None,
            height=None,
        )

    async def _fake_download_image_bytes(url: str):
        assert url == "https://example.com/generated-2.png"
        return b"fake-png-binary-2"

    monkeypatch.setattr(
        "newbee_notebook.core.tools.image_generation.qwen_generate_image",
        _fake_qwen_generate_image,
    )
    monkeypatch.setattr(
        "newbee_notebook.core.tools.image_generation._download_image_bytes",
        _fake_download_image_bytes,
    )

    storage = AsyncMock()
    storage.save_file = AsyncMock(return_value="generated-images/nb-1/s-1/img-2.png")
    save_record = AsyncMock(return_value=None)

    tool = build_image_generation_tool(
        ImageToolContext(
            session_id="s-1",
            notebook_id="nb-1",
            provider="qwen",
            api_key="sk-test",
            storage=storage,
            save_record=save_record,
        )
    )

    result = await tool.execute(
        {
            "prompt": "a cover bee",
            "width": 768,
            "height": 512,
        }
    )

    assert captured["size"] == "768*512"
    assert result.error is None
    assert result.images[0].width == 768
    assert result.images[0].height == 512
    assert save_record.await_args.kwargs["size"] == "768*512"
    assert save_record.await_args.kwargs["width"] == 768
    assert save_record.await_args.kwargs["height"] == 512


@pytest.mark.anyio
async def test_image_generate_tool_uses_provider_default_dimensions_when_omitted(
    monkeypatch,
):
    monkeypatch.setattr(
        "newbee_notebook.core.tools.image_generation.generate_uuid",
        lambda: "img-3",
    )

    captured: dict[str, object] = {}

    async def _fake_zhipu_generate_image(**kwargs):
        captured.update(kwargs)
        return ImageAPIResult(
            image_urls=["https://example.com/generated-3.png"],
            model="glm-image",
            width=None,
            height=None,
        )

    async def _fake_download_image_bytes(url: str):
        assert url == "https://example.com/generated-3.png"
        return b"fake-png-binary-3"

    monkeypatch.setattr(
        "newbee_notebook.core.tools.image_generation.zhipu_generate_image",
        _fake_zhipu_generate_image,
    )
    monkeypatch.setattr(
        "newbee_notebook.core.tools.image_generation._download_image_bytes",
        _fake_download_image_bytes,
    )

    storage = AsyncMock()
    storage.save_file = AsyncMock(return_value="generated-images/nb-1/s-1/img-3.png")
    save_record = AsyncMock(return_value=None)

    tool = build_image_generation_tool(
        ImageToolContext(
            session_id="s-1",
            notebook_id="nb-1",
            provider="zhipu",
            api_key="sk-test",
            storage=storage,
            save_record=save_record,
        )
    )

    result = await tool.execute({"prompt": "a warm bee"})

    assert captured["size"] == "1280x1280"
    assert result.error is None
    assert result.images[0].width == 1280
    assert result.images[0].height == 1280
    assert save_record.await_args.kwargs["size"] == "1280x1280"
    assert save_record.await_args.kwargs["width"] == 1280
    assert save_record.await_args.kwargs["height"] == 1280


@pytest.mark.anyio
async def test_image_generate_tool_retries_retryable_api_failure(monkeypatch):
    monkeypatch.setattr(
        "newbee_notebook.core.tools.image_generation.generate_uuid",
        lambda: "img-retry",
    )
    monkeypatch.setattr("newbee_notebook.core.tools.image_generation.IMAGE_RETRY_DELAY_SECONDS", 0)

    attempts = {"qwen": 0}

    async def _flaky_qwen_generate_image(**kwargs):
        attempts["qwen"] += 1
        if attempts["qwen"] == 1:
            raise requests.exceptions.ConnectionError("temporary image API break")
        return ImageAPIResult(
            image_urls=["https://example.com/retry.png"],
            model="qwen-image-2.0-pro",
            width=1024,
            height=1024,
        )

    async def _fake_download_image_bytes(url: str):
        assert url == "https://example.com/retry.png"
        return b"retry-png-binary"

    monkeypatch.setattr(
        "newbee_notebook.core.tools.image_generation.qwen_generate_image",
        _flaky_qwen_generate_image,
    )
    monkeypatch.setattr(
        "newbee_notebook.core.tools.image_generation._download_image_bytes",
        _fake_download_image_bytes,
    )

    storage = AsyncMock()
    storage.save_file = AsyncMock(return_value="generated-images/nb-1/s-1/img-retry.png")
    save_record = AsyncMock(return_value=None)

    tool = build_image_generation_tool(
        ImageToolContext(
            session_id="s-1",
            notebook_id="nb-1",
            provider="qwen",
            api_key="sk-test",
            storage=storage,
            save_record=save_record,
        )
    )

    result = await tool.execute({"prompt": "a resilient bee"})

    assert result.error is None
    assert attempts["qwen"] == 2
    assert len(result.images) == 1
    storage.save_file.assert_awaited_once()


@pytest.mark.anyio
async def test_image_generate_tool_reports_save_failure_separately(monkeypatch):
    async def _fake_qwen_generate_image(**kwargs):
        return ImageAPIResult(
            image_urls=["https://example.com/save-fails.png"],
            model="qwen-image-2.0-pro",
            width=1024,
            height=1024,
        )

    async def _failing_download_image_bytes(url: str):
        raise RuntimeError("download failed")

    monkeypatch.setattr(
        "newbee_notebook.core.tools.image_generation.qwen_generate_image",
        _fake_qwen_generate_image,
    )
    monkeypatch.setattr(
        "newbee_notebook.core.tools.image_generation._download_image_bytes",
        _failing_download_image_bytes,
    )

    storage = AsyncMock()
    save_record = AsyncMock(return_value=None)

    tool = build_image_generation_tool(
        ImageToolContext(
            session_id="s-1",
            notebook_id="nb-1",
            provider="qwen",
            api_key="sk-test",
            storage=storage,
            save_record=save_record,
        )
    )

    result = await tool.execute({"prompt": "a bee that cannot be saved"})

    assert result.content == ""
    assert result.error == "image save failed: download failed"
    storage.save_file.assert_not_called()
    save_record.assert_not_called()
