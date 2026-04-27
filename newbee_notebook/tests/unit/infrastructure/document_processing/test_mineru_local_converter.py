import asyncio
import json

import requests
import pytest

from newbee_notebook.infrastructure.document_processing.converters.mineru_local_converter import (
    MinerULocalConverter,
)


class _Response:
    headers = {"content-type": "application/zip"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=1024 * 1024):  # noqa: ARG002
        yield b"PK\x03\x04"


def test_convert_range_sends_new_local_form_fields(monkeypatch, tmp_path):
    pdf_path = tmp_path / "demo.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    captured: dict[str, object] = {}

    def _fake_post(url, files, data, timeout, stream):  # noqa: ANN001
        captured["url"] = url
        captured["data"] = list(data)
        captured["timeout"] = timeout
        captured["stream"] = stream
        captured["mime_type"] = files["files"][2]
        assert "files" in files
        return _Response()

    monkeypatch.setattr(requests, "post", _fake_post)
    monkeypatch.setattr(
        MinerULocalConverter,
        "_parse_result_zip",
        staticmethod(lambda _zip_source: ("# ok", {}, {})),
    )

    converter = MinerULocalConverter(
        parse_method="ocr",
        formula_enable=False,
        table_enable=True,
    )

    result = asyncio.run(converter._convert_range(pdf_path, start_page=0, end_page=0))

    assert result.markdown == "# ok"
    assert ("parse_method", "ocr") in captured["data"]
    assert ("formula_enable", "false") in captured["data"]
    assert ("table_enable", "true") in captured["data"]
    assert ("start_page_id", "0") in captured["data"]
    assert ("end_page_id", "0") in captured["data"]
    assert captured["mime_type"] == "application/pdf"


@pytest.mark.parametrize(
    ("ext", "expected_mime"),
    [
        (".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        (".pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        (".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        (".png", "image/png"),
    ],
)
def test_convert_non_pdf_omits_pagination_and_uses_real_mime(
    monkeypatch,
    tmp_path,
    ext: str,
    expected_mime: str,
):
    file_path = tmp_path / f"demo{ext}"
    file_path.write_bytes(b"demo-content")
    captured: dict[str, object] = {}

    def _fake_post(url, files, data, timeout, stream):  # noqa: ANN001
        captured["url"] = url
        captured["data"] = list(data)
        captured["timeout"] = timeout
        captured["stream"] = stream
        captured["mime_type"] = files["files"][2]
        return _Response()

    monkeypatch.setattr(requests, "post", _fake_post)
    monkeypatch.setattr(
        MinerULocalConverter,
        "_parse_result_zip",
        staticmethod(
            lambda _zip_source: (
                "# non-pdf-ok",
                {},
                {"content_list_v2.json": json.dumps([{}, {}, {}]).encode("utf-8")},
            )
        ),
    )

    async def _count_pages_must_not_run(_path):  # noqa: ANN001
        raise AssertionError("_count_pages should not run for non-PDF files")

    converter = MinerULocalConverter(
        parse_method="ocr",
        formula_enable=True,
        table_enable=False,
    )
    monkeypatch.setattr(converter, "_count_pages", _count_pages_must_not_run)

    result = asyncio.run(converter.convert(str(file_path)))

    assert result.markdown == "# non-pdf-ok"
    assert result.page_count == 3
    assert ("parse_method", "ocr") in captured["data"]
    assert ("formula_enable", "true") in captured["data"]
    assert ("table_enable", "false") in captured["data"]
    assert ("start_page_id", "0") not in captured["data"]
    assert ("end_page_id", "0") not in captured["data"]
    assert captured["mime_type"] == expected_mime


@pytest.mark.parametrize(
    ("ext", "expected"),
    [
        (".pdf", True),
        (".docx", True),
        (".pptx", True),
        (".xlsx", True),
        (".png", True),
        (".jpg", True),
        (".doc", False),
        (".ppt", False),
        (".html", False),
        ("", False),
    ],
)
def test_can_handle_matches_official_local_support_set(ext: str, expected: bool):
    converter = MinerULocalConverter()
    assert converter.can_handle(ext) is expected

