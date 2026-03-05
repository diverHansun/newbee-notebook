"""Tests for document processing configuration and converter selection."""

import asyncio
import time

import requests
import pytest

from newbee_notebook.core.common.config import get_document_processing_config
from newbee_notebook.infrastructure.document_processing.processor import DocumentProcessor
from newbee_notebook.infrastructure.document_processing.converters.base import ConversionResult
from newbee_notebook.infrastructure.document_processing.converters.markitdown_converter import (
    MarkItDownConverter,
)
from newbee_notebook.infrastructure.document_processing.converters.mineru_cloud_converter import (
    MinerUCloudConverter,
    MinerUCloudTransientError,
)
from newbee_notebook.infrastructure.document_processing.converters.mineru_local_converter import (
    MinerULocalConverter,
)


def _base_config() -> dict:
    return {
        "document_processing": {
            "documents_dir": "data/documents",
            "mineru_enabled": True,
            "mineru_mode": "cloud",
            "mineru_cloud": {
                "api_key": "mineru-api-key-123",
                "api_base": "https://mineru.net",
                "timeout_seconds": 60,
                "poll_interval": 5,
                "max_wait_seconds": 1800,
            },
            "mineru_local": {
                "api_url": "http://mineru-api:8000",
                "backend": "pipeline",
                "lang_list": "ch,en",
                "timeout_seconds": 0,
            },
            "fail_threshold": 5,
            "cooldown_seconds": 120,
        }
    }


def test_get_document_processing_config_resolves_nested_env(monkeypatch):
    monkeypatch.setenv("MINERU_MODE", "cloud")
    monkeypatch.setenv("MINERU_API_KEY", "api-key-from-env")
    monkeypatch.setenv("MINERU_LOCAL_API_URL", "http://mineru-api:8000")

    cfg = get_document_processing_config()
    dp_cfg = cfg["document_processing"]
    assert dp_cfg["mineru_mode"] == "cloud"
    assert dp_cfg["mineru_cloud"]["api_key"] == "api-key-from-env"
    assert dp_cfg["mineru_local"]["api_url"] == "http://mineru-api:8000"


def test_get_document_processing_config_supports_empty_default(monkeypatch):
    monkeypatch.delenv("MINERU_API_KEY", raising=False)
    cfg = get_document_processing_config()
    assert cfg["document_processing"]["mineru_cloud"]["api_key"] == ""


def test_processor_cloud_mode_uses_cloud_converter():
    cfg = _base_config()
    processor = DocumentProcessor(config=cfg)

    pdf_converters = processor._get_converters_for_ext(".pdf")
    assert len(pdf_converters) == 2
    assert isinstance(pdf_converters[0], MinerUCloudConverter)
    assert isinstance(pdf_converters[1], MarkItDownConverter)


def test_processor_cloud_mode_without_api_key_skips_mineru():
    cfg = _base_config()
    cfg["document_processing"]["mineru_cloud"]["api_key"] = ""
    processor = DocumentProcessor(config=cfg)

    pdf_converters = processor._get_converters_for_ext(".pdf")
    assert len(pdf_converters) == 1
    assert isinstance(pdf_converters[0], MarkItDownConverter)


def test_processor_local_mode_uses_local_converter():
    cfg = _base_config()
    cfg["document_processing"]["mineru_mode"] = "local"
    processor = DocumentProcessor(config=cfg)

    pdf_converters = processor._get_converters_for_ext(".pdf")
    assert len(pdf_converters) == 2
    assert isinstance(pdf_converters[0], MinerULocalConverter)
    assert isinstance(pdf_converters[1], MarkItDownConverter)


def test_processor_local_mode_enables_metadata_by_default():
    cfg = _base_config()
    cfg["document_processing"]["mineru_mode"] = "local"
    cfg["document_processing"]["mineru_local"].pop("return_content_list", None)
    cfg["document_processing"]["mineru_local"].pop("return_model_output", None)
    processor = DocumentProcessor(config=cfg)

    mineru_local = next(c for c in processor._converters if isinstance(c, MinerULocalConverter))
    assert mineru_local._return_content_list is True
    assert mineru_local._return_model_output is True


def test_processor_local_mode_allows_disabling_metadata_flags():
    cfg = _base_config()
    cfg["document_processing"]["mineru_mode"] = "local"
    cfg["document_processing"]["mineru_local"]["return_content_list"] = False
    cfg["document_processing"]["mineru_local"]["return_model_output"] = False
    processor = DocumentProcessor(config=cfg)

    mineru_local = next(c for c in processor._converters if isinstance(c, MinerULocalConverter))
    assert mineru_local._return_content_list is False
    assert mineru_local._return_model_output is False


def test_processor_invalid_mode_disables_mineru():
    cfg = _base_config()
    cfg["document_processing"]["mineru_mode"] = "invalid"
    processor = DocumentProcessor(config=cfg)

    pdf_converters = processor._get_converters_for_ext(".pdf")
    assert len(pdf_converters) == 1
    assert isinstance(pdf_converters[0], MarkItDownConverter)


@pytest.mark.parametrize("ext", [".doc", ".docx"])
def test_processor_cloud_mode_office_prefers_mineru_then_markitdown(ext: str):
    cfg = _base_config()
    processor = DocumentProcessor(config=cfg)

    converters = processor._get_converters_for_ext(ext)
    assert len(converters) == 2
    assert isinstance(converters[0], MinerUCloudConverter)
    assert isinstance(converters[1], MarkItDownConverter)


def test_processor_cloud_mode_pptx_uses_markitdown_only():
    cfg = _base_config()
    processor = DocumentProcessor(config=cfg)

    converters = processor._get_converters_for_ext(".pptx")
    assert len(converters) == 1
    assert isinstance(converters[0], MarkItDownConverter)

def test_processor_trips_cooldown_after_five_consecutive_mineru_failures(monkeypatch):
    cfg = _base_config()
    cfg["document_processing"]["fail_threshold"] = 5
    cfg["document_processing"]["cooldown_seconds"] = 120
    processor = DocumentProcessor(config=cfg)

    mineru = next(c for c in processor._converters if isinstance(c, MinerUCloudConverter))
    markitdown = next(c for c in processor._converters if isinstance(c, MarkItDownConverter))

    async def _mineru_fail(_file_path: str):
        raise requests.RequestException("network unavailable")

    async def _fallback_ok(_file_path: str):
        return ConversionResult(markdown="# fallback")

    monkeypatch.setattr(mineru, "convert", _mineru_fail)
    monkeypatch.setattr(markitdown, "convert", _fallback_ok)

    async def _run():
        for idx in range(5):
            result = await processor.convert("sample.pdf")
            assert result.markdown == "# fallback"
            if idx < 4:
                assert processor._mineru_unavailable_until <= time.monotonic()

    asyncio.run(_run())
    assert processor._mineru_unavailable_until > time.monotonic()


def test_processor_resets_failure_counter_after_mineru_success(monkeypatch):
    cfg = _base_config()
    cfg["document_processing"]["fail_threshold"] = 5
    processor = DocumentProcessor(config=cfg)

    mineru = next(c for c in processor._converters if isinstance(c, MinerUCloudConverter))
    markitdown = next(c for c in processor._converters if isinstance(c, MarkItDownConverter))

    calls = {"count": 0}

    async def _mineru_flaky(_file_path: str):
        calls["count"] += 1
        if calls["count"] == 1:
            raise requests.RequestException("temporary error")
        return ConversionResult(markdown="# mineru")

    async def _fallback_ok(_file_path: str):
        return ConversionResult(markdown="# fallback")

    monkeypatch.setattr(mineru, "convert", _mineru_flaky)
    monkeypatch.setattr(markitdown, "convert", _fallback_ok)

    async def _run():
        first = await processor.convert("sample.pdf")
        assert first.markdown == "# fallback"
        assert processor._mineru_consecutive_failures == 1

        second = await processor.convert("sample.pdf")
        assert second.markdown == "# mineru"
        assert processor._mineru_consecutive_failures == 0

    asyncio.run(_run())


def test_processor_trips_cooldown_on_mineru_cdn_transient_error(monkeypatch):
    cfg = _base_config()
    cfg["document_processing"]["fail_threshold"] = 1
    cfg["document_processing"]["cooldown_seconds"] = 120
    processor = DocumentProcessor(config=cfg)

    mineru = next(c for c in processor._converters if isinstance(c, MinerUCloudConverter))
    markitdown = next(c for c in processor._converters if isinstance(c, MarkItDownConverter))

    async def _mineru_fail(_file_path: str):
        raise MinerUCloudTransientError("MinerU CDN download failed after 3 retries")

    async def _fallback_ok(_file_path: str):
        return ConversionResult(markdown="# fallback")

    monkeypatch.setattr(mineru, "convert", _mineru_fail)
    monkeypatch.setattr(markitdown, "convert", _fallback_ok)

    result = asyncio.run(processor.convert("sample.pdf"))
    assert result.markdown == "# fallback"
    assert processor._mineru_unavailable_until > time.monotonic()


def test_processor_error_chain_preserves_root_cause(monkeypatch):
    cfg = _base_config()
    processor = DocumentProcessor(config=cfg)

    mineru = next(c for c in processor._converters if isinstance(c, MinerUCloudConverter))
    markitdown = next(c for c in processor._converters if isinstance(c, MarkItDownConverter))

    async def _mineru_fail(_file_path: str):
        raise MinerUCloudTransientError("MinerU CDN download failed after 3 retries")

    async def _markitdown_fail(_file_path: str):
        raise RuntimeError("MarkItDown produced empty markdown")

    monkeypatch.setattr(mineru, "convert", _mineru_fail)
    monkeypatch.setattr(markitdown, "convert", _markitdown_fail)

    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(processor.convert("sample.pdf"))

    text = str(exc_info.value)
    assert "First error (MinerUCloudConverter)" in text
    assert "MinerU CDN download failed after 3 retries" in text
    assert "Last error (MarkItDownConverter)" in text
    assert "MarkItDown produced empty markdown" in text
