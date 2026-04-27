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
    MinerUCloudLimitExceededError,
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


def test_get_document_processing_config_resolves_mineru_local_stability_env(monkeypatch):
    monkeypatch.setenv("MINERU_LOCAL_MAX_PAGES_PER_BATCH", "50")
    monkeypatch.setenv("MINERU_LOCAL_REQUEST_RETRY_ATTEMPTS", "2")
    monkeypatch.setenv("MINERU_LOCAL_RETRY_BACKOFF_SECONDS", "10")

    cfg = get_document_processing_config()
    local_cfg = cfg["document_processing"]["mineru_local"]
    assert local_cfg["max_pages_per_batch"] == "50"
    assert local_cfg["request_retry_attempts"] == "2"
    assert local_cfg["retry_backoff_seconds"] == "10"


def test_get_document_processing_config_resolves_new_mineru_30_env(monkeypatch):
    monkeypatch.setenv("MINERU_CLOUD_MODEL_VERSION", "vlm")
    monkeypatch.setenv("MINERU_CLOUD_ENABLE_FORMULA", "false")
    monkeypatch.setenv("MINERU_CLOUD_ENABLE_TABLE", "true")
    monkeypatch.setenv("MINERU_CLOUD_IS_OCR", "true")
    monkeypatch.setenv("MINERU_CLOUD_LANGUAGE", "en")
    monkeypatch.setenv("MINERU_LOCAL_PARSE_METHOD", "ocr")
    monkeypatch.setenv("MINERU_LOCAL_FORMULA_ENABLE", "false")
    monkeypatch.setenv("MINERU_LOCAL_TABLE_ENABLE", "true")

    cfg = get_document_processing_config()["document_processing"]

    assert cfg["mineru_cloud"]["model_version"] == "vlm"
    assert cfg["mineru_cloud"]["enable_formula"] == "false"
    assert cfg["mineru_cloud"]["enable_table"] == "true"
    assert cfg["mineru_cloud"]["is_ocr"] == "true"
    assert cfg["mineru_cloud"]["language"] == "en"
    assert cfg["mineru_local"]["parse_method"] == "ocr"
    assert cfg["mineru_local"]["formula_enable"] == "false"
    assert cfg["mineru_local"]["table_enable"] == "true"


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


def test_processor_cloud_mode_wires_new_v4_options():
    cfg = _base_config()
    cfg["document_processing"]["mineru_cloud"].update(
        {
            "model_version": "vlm",
            "enable_formula": False,
            "enable_table": True,
            "is_ocr": "false",
            "language": "en",
        }
    )
    processor = DocumentProcessor(config=cfg)

    mineru_cloud = next(c for c in processor._converters if isinstance(c, MinerUCloudConverter))
    assert mineru_cloud._model_version == "vlm"
    assert mineru_cloud._enable_formula is False
    assert mineru_cloud._enable_table is True
    assert mineru_cloud._is_ocr is False
    assert mineru_cloud._language == "en"


def test_processor_local_mode_uses_local_converter():
    cfg = _base_config()
    cfg["document_processing"]["mineru_mode"] = "local"
    processor = DocumentProcessor(config=cfg)

    pdf_converters = processor._get_converters_for_ext(".pdf")
    assert len(pdf_converters) == 2
    assert isinstance(pdf_converters[0], MinerULocalConverter)
    assert isinstance(pdf_converters[1], MarkItDownConverter)


@pytest.mark.parametrize(
    ("ext", "expected_types"),
    [
        (".pdf", [MinerULocalConverter, MarkItDownConverter]),
        (".docx", [MinerULocalConverter, MarkItDownConverter]),
        (".pptx", [MinerULocalConverter, MarkItDownConverter]),
        (".xlsx", [MinerULocalConverter, MarkItDownConverter]),
        (".png", [MinerULocalConverter]),
        (".jpg", [MinerULocalConverter]),
        (".jpeg", [MinerULocalConverter]),
        (".bmp", [MinerULocalConverter]),
        (".webp", [MinerULocalConverter]),
        (".gif", [MinerULocalConverter]),
        (".jp2", [MinerULocalConverter]),
        (".tif", [MinerULocalConverter]),
        (".tiff", [MinerULocalConverter]),
    ],
)
def test_processor_local_mode_official_supported_types_prefer_local_converter(ext: str, expected_types: list[type]):
    cfg = _base_config()
    cfg["document_processing"]["mineru_mode"] = "local"
    processor = DocumentProcessor(config=cfg)

    converters = processor._get_converters_for_ext(ext)
    assert [type(c) for c in converters] == expected_types


@pytest.mark.parametrize("ext", [".doc", ".ppt", ".html", ".htm"])
def test_processor_local_mode_cloud_only_types_do_not_route_to_local(ext: str):
    cfg = _base_config()
    cfg["document_processing"]["mineru_mode"] = "local"
    processor = DocumentProcessor(config=cfg)

    converters = processor._get_converters_for_ext(ext)
    assert converters
    assert isinstance(converters[0], MarkItDownConverter)
    assert all(not isinstance(c, MinerULocalConverter) for c in converters)


def test_processor_local_mode_wires_new_local_options():
    cfg = _base_config()
    cfg["document_processing"]["mineru_mode"] = "local"
    cfg["document_processing"]["mineru_local"].update(
        {
            "parse_method": "ocr",
            "formula_enable": False,
            "table_enable": True,
        }
    )
    processor = DocumentProcessor(config=cfg)

    mineru_local = next(c for c in processor._converters if isinstance(c, MinerULocalConverter))
    assert mineru_local._parse_method == "ocr"
    assert mineru_local._formula_enable is False
    assert mineru_local._table_enable is True


def test_processor_local_mode_uses_batch_size_50_by_default():
    cfg = _base_config()
    cfg["document_processing"]["mineru_mode"] = "local"
    cfg["document_processing"]["mineru_local"].pop("max_pages_per_batch", None)
    processor = DocumentProcessor(config=cfg)

    mineru_local = next(c for c in processor._converters if isinstance(c, MinerULocalConverter))
    assert mineru_local._max_pages_per_batch == 50


def test_processor_local_mode_wires_retry_settings_from_config():
    cfg = _base_config()
    cfg["document_processing"]["mineru_mode"] = "local"
    cfg["document_processing"]["mineru_local"]["request_retry_attempts"] = "4"
    cfg["document_processing"]["mineru_local"]["retry_backoff_seconds"] = "1.5"
    processor = DocumentProcessor(config=cfg)

    mineru_local = next(c for c in processor._converters if isinstance(c, MinerULocalConverter))
    assert mineru_local._request_retry_attempts == 4
    assert mineru_local._retry_backoff_seconds == 1.5


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


@pytest.mark.parametrize("ext", [".ppt", ".pptx", ".html", ".htm"])
def test_processor_cloud_mode_new_document_types_prefer_mineru_then_markitdown(ext: str):
    cfg = _base_config()
    processor = DocumentProcessor(config=cfg)

    converters = processor._get_converters_for_ext(ext)
    assert len(converters) == 2
    assert isinstance(converters[0], MinerUCloudConverter)
    assert isinstance(converters[1], MarkItDownConverter)


@pytest.mark.parametrize("ext", [".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".jp2", ".tif", ".tiff"])
def test_processor_cloud_mode_images_use_mineru_only(ext: str):
    cfg = _base_config()
    processor = DocumentProcessor(config=cfg)

    converters = processor._get_converters_for_ext(ext)
    assert len(converters) == 1
    assert isinstance(converters[0], MinerUCloudConverter)


def test_processor_cloud_mode_epub_uses_markitdown_only():
    cfg = _base_config()
    processor = DocumentProcessor(config=cfg)

    converters = processor._get_converters_for_ext(".epub")
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


def test_processor_falls_back_without_cooldown_when_cloud_limit_exceeded(monkeypatch):
    cfg = _base_config()
    cfg["document_processing"]["fail_threshold"] = 1
    processor = DocumentProcessor(config=cfg)

    mineru = next(c for c in processor._converters if isinstance(c, MinerUCloudConverter))
    markitdown = next(c for c in processor._converters if isinstance(c, MarkItDownConverter))

    async def _mineru_limit(_file_path: str):
        raise MinerUCloudLimitExceededError("MinerU cloud page limit exceeded")

    async def _fallback_ok(_file_path: str):
        return ConversionResult(markdown="# fallback")

    monkeypatch.setattr(mineru, "convert", _mineru_limit)
    monkeypatch.setattr(markitdown, "convert", _fallback_ok)

    result = asyncio.run(processor.convert("sample.html"))

    assert result.markdown == "# fallback"
    assert processor._mineru_unavailable_until <= time.monotonic()
    assert processor._mineru_consecutive_failures == 0


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


def test_local_converter_retries_transient_batch_failure(monkeypatch, tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    converter = MinerULocalConverter(request_retry_attempts=2, retry_backoff_seconds=0.0)

    async def _count_pages(_path):
        return 1

    calls = {"count": 0}

    async def _convert_range(_path, *, start_page, end_page):
        calls["count"] += 1
        if calls["count"] == 1:
            response = requests.Response()
            response.status_code = 500
            response.url = "http://mineru-api:8000/file_parse"
            raise requests.HTTPError(response=response)
        return ConversionResult(markdown="# recovered", page_count=1)

    monkeypatch.setattr(converter, "_count_pages", _count_pages)
    monkeypatch.setattr(converter, "_convert_range", _convert_range)

    result = asyncio.run(converter.convert(str(pdf_path)))

    assert result.markdown == "# recovered"
    assert calls["count"] == 2
