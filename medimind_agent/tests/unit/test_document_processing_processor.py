"""Tests for document processing configuration and converter selection."""

from medimind_agent.core.common.config import get_document_processing_config
from medimind_agent.infrastructure.document_processing.processor import DocumentProcessor
from medimind_agent.infrastructure.document_processing.converters.markitdown_converter import (
    MarkItDownConverter,
)
from medimind_agent.infrastructure.document_processing.converters.mineru_cloud_converter import (
    MinerUCloudConverter,
)
from medimind_agent.infrastructure.document_processing.converters.mineru_local_converter import (
    MinerULocalConverter,
)
from medimind_agent.infrastructure.document_processing.converters.pypdf_converter import (
    PyPdfConverter,
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
            "unavailable_cooldown_seconds": 300,
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
    assert isinstance(pdf_converters[1], PyPdfConverter)


def test_processor_cloud_mode_without_api_key_skips_mineru():
    cfg = _base_config()
    cfg["document_processing"]["mineru_cloud"]["api_key"] = ""
    processor = DocumentProcessor(config=cfg)

    pdf_converters = processor._get_converters_for_ext(".pdf")
    assert len(pdf_converters) == 1
    assert isinstance(pdf_converters[0], PyPdfConverter)


def test_processor_local_mode_uses_local_converter():
    cfg = _base_config()
    cfg["document_processing"]["mineru_mode"] = "local"
    processor = DocumentProcessor(config=cfg)

    pdf_converters = processor._get_converters_for_ext(".pdf")
    assert len(pdf_converters) == 2
    assert isinstance(pdf_converters[0], MinerULocalConverter)
    assert isinstance(pdf_converters[1], PyPdfConverter)


def test_processor_invalid_mode_disables_mineru():
    cfg = _base_config()
    cfg["document_processing"]["mineru_mode"] = "invalid"
    processor = DocumentProcessor(config=cfg)

    pdf_converters = processor._get_converters_for_ext(".pdf")
    assert len(pdf_converters) == 1
    assert isinstance(pdf_converters[0], PyPdfConverter)


def test_processor_non_pdf_uses_markitdown():
    cfg = _base_config()
    processor = DocumentProcessor(config=cfg)

    docx_converters = processor._get_converters_for_ext(".docx")
    assert len(docx_converters) == 1
    assert isinstance(docx_converters[0], MarkItDownConverter)
