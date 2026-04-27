import asyncio

import pytest
import requests

from newbee_notebook.infrastructure.document_processing.converters.mineru_cloud_converter import (
    MinerUCloudConverter,
    MinerUCloudLimitExceededError,
)


def test_request_upload_url_includes_new_v4_payload_fields(monkeypatch):
    captured: dict[str, object] = {}

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"code": 0, "data": {"batch_id": "batch-1", "file_urls": ["https://upload.example"]}}

    def _fake_post(url, headers, json, timeout):  # noqa: ANN001
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(requests, "post", _fake_post)

    converter = MinerUCloudConverter(
        api_key="dummy-key",
        model_version="vlm",
        enable_formula=False,
        enable_table=True,
        is_ocr=False,
        language="en",
    )

    batch_id, upload_url = converter._request_upload_url("demo.pdf")

    assert batch_id == "batch-1"
    assert upload_url == "https://upload.example"
    assert captured["url"] == "https://mineru.net/api/v4/file-urls/batch"
    assert captured["json"] == {
        "files": [{"name": "demo.pdf", "is_ocr": False}],
        "model_version": "vlm",
        "enable_formula": False,
        "enable_table": True,
        "language": "en",
    }


def test_request_upload_url_omits_none_optional_fields(monkeypatch):
    captured: dict[str, object] = {}

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"code": 0, "data": {"batch_id": "batch-2", "file_urls": ["https://upload.example"]}}

    def _fake_post(url, headers, json, timeout):  # noqa: ANN001
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(requests, "post", _fake_post)

    converter = MinerUCloudConverter(
        api_key="dummy-key",
        model_version="",
        is_ocr=None,
    )

    converter._request_upload_url("demo.pdf")

    assert captured["json"] == {
        "files": [{"name": "demo.pdf"}],
        "enable_formula": True,
        "enable_table": True,
        "language": "ch",
    }


@pytest.mark.parametrize(
    "ext",
    [".ppt", ".pptx", ".html", ".htm", ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".jp2", ".tif", ".tiff"],
)
def test_cloud_converter_supports_new_extensions(ext: str):
    converter = MinerUCloudConverter(api_key="dummy-key")
    assert converter.can_handle(ext) is True


def test_request_upload_url_routes_html_to_mineru_html(monkeypatch):
    captured: dict[str, object] = {}

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"code": 0, "data": {"batch_id": "batch-html", "file_urls": ["https://upload.example"]}}

    def _fake_post(url, headers, json, timeout):  # noqa: ANN001
        captured["json"] = json
        return _Response()

    monkeypatch.setattr(requests, "post", _fake_post)

    converter = MinerUCloudConverter(api_key="dummy-key", model_version="vlm")

    converter._request_upload_url("demo.html")

    assert captured["json"] == {
        "files": [{"name": "demo.html"}],
        "model_version": "MinerU-HTML",
        "enable_formula": True,
        "enable_table": True,
        "language": "ch",
    }


def test_request_upload_url_ignores_mineru_html_for_non_html(monkeypatch):
    captured: dict[str, object] = {}

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"code": 0, "data": {"batch_id": "batch-pdf", "file_urls": ["https://upload.example"]}}

    def _fake_post(url, headers, json, timeout):  # noqa: ANN001
        captured["json"] = json
        return _Response()

    monkeypatch.setattr(requests, "post", _fake_post)

    converter = MinerUCloudConverter(api_key="dummy-key", model_version="MinerU-HTML")

    converter._request_upload_url("demo.pdf")

    assert captured["json"] == {
        "files": [{"name": "demo.pdf"}],
        "enable_formula": True,
        "enable_table": True,
        "language": "ch",
    }


def test_convert_rejects_pdf_over_200_pages_before_request(monkeypatch, tmp_path):
    pdf_path = tmp_path / "oversized.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    converter = MinerUCloudConverter(api_key="dummy-key")

    async def _count_pages(_path):
        return 201

    def _unexpected_post(*args, **kwargs):  # noqa: ARG001
        raise AssertionError("cloud upload url should not be requested for oversized pdf")

    monkeypatch.setattr(converter, "_count_pages", _count_pages)
    monkeypatch.setattr(requests, "post", _unexpected_post)

    with pytest.raises(MinerUCloudLimitExceededError):
        asyncio.run(converter.convert(str(pdf_path)))


def test_convert_rejects_file_over_200mb_before_request(monkeypatch, tmp_path):
    big_path = tmp_path / "oversized.docx"
    with big_path.open("wb") as handle:
        handle.truncate((200 * 1024 * 1024) + 1)

    converter = MinerUCloudConverter(api_key="dummy-key")

    def _unexpected_post(*args, **kwargs):  # noqa: ARG001
        raise AssertionError("cloud upload url should not be requested for oversized file")

    monkeypatch.setattr(requests, "post", _unexpected_post)

    with pytest.raises(MinerUCloudLimitExceededError):
        asyncio.run(converter.convert(str(big_path)))
