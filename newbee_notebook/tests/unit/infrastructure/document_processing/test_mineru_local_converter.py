import asyncio
import json
import io
import zipfile

import requests
import pytest

from newbee_notebook.infrastructure.document_processing.converters.mineru_local_converter import (
    MinerULocalConverter,
)
from newbee_notebook.infrastructure.document_processing.converters.base import ConversionResult


class _Response:
    status_code = 200
    headers = {"content-type": "application/zip"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False

    def raise_for_status(self):
        return None

    def close(self):
        pass

    def iter_content(self, chunk_size=1024 * 1024):  # noqa: ARG002
        yield b"PK\x03\x04"


@pytest.mark.parametrize("api_version", ["legacy", "v1"])
def test_batched_pdf_preserves_image_references_on_name_collision(monkeypatch, tmp_path, api_version):
    path = tmp_path / "figures.pdf"
    path.write_bytes(b"pdf")
    converter = MinerULocalConverter(api_version=api_version, max_pages_per_batch=1)

    async def count_pages(_path):
        return 2

    async def convert_range(_path, *, start_page, end_page):
        return ConversionResult(
            markdown='![figure](images/chart.jpg)\n<img src="images/chart.jpg">',
            page_count=1,
            image_assets={"images/chart.jpg": bytes([start_page])},
        )

    monkeypatch.setattr(converter, "_count_pages", count_pages)
    monkeypatch.setattr(converter, "_convert_range_with_retry", convert_range)
    result = asyncio.run(converter.convert(str(path)))
    assert result.page_count == 2
    assert result.image_assets == {"images/chart.jpg": b"\x00", "batch2/images/chart.jpg": b"\x01"}
    assert result.markdown.count("](images/chart.jpg)") == 1
    assert "](batch2/images/chart.jpg)" in result.markdown
    assert '<img src="batch2/images/chart.jpg">' in result.markdown


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


def test_v1_sends_query_options_and_preserves_pages_and_assets(monkeypatch, tmp_path):
    path = tmp_path / "中文 文件.pdf"
    path.write_bytes(b"pdf")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("document.md", "# Local\n![plot](images/plot.png)")
        z.writestr("images/plot.png", b"image")
        z.writestr("middle_json.json", json.dumps({"schema": "2.0", "pages": [{}, {}]}))

    class Response(_Response):
        status_code = 200

        def iter_content(self, chunk_size):
            yield archive.getvalue()

    def post(url, files, params, timeout, stream):
        assert url == "http://localhost:8001/v1/file_parse"
        assert files["files"][0] == path.name
        assert dict(params) == {
            "tier": "standard", "ocr_mode": "ocr", "page_range": "3-4",
            "response_format": "zip", "wait_timeout": "30",
        }
        return Response()

    monkeypatch.setattr(requests, "post", post)
    converter = MinerULocalConverter(base_url="http://localhost:8001", api_version="v1", parse_method="ocr")
    result = asyncio.run(converter._convert_range(path, start_page=2, end_page=3))
    assert result.page_count == 2
    assert result.image_assets == {"images/plot.png": b"image"}
    assert "middle_json.json" in result.metadata_assets


def test_v1_native_documents_use_flash(monkeypatch, tmp_path):
    path = tmp_path / "demo.docx"
    path.write_bytes(b"docx")

    def post(url, files, params, timeout, stream):
        assert dict(params)["tier"] == "flash"
        assert "page_range" not in dict(params)
        return _Response()

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(MinerULocalConverter, "_parse_result_zip", staticmethod(lambda _: ("ok", {}, {})))
    converter = MinerULocalConverter(api_version="v1")
    asyncio.run(converter.convert(str(path)))


def test_v1_accepted_job_is_polled_without_resubmitting(monkeypatch):
    calls = []

    class Accepted(_Response):
        status_code = 202

        def json(self):
            return {"task_id": "job-1", "result_url": "https://untrusted.example/result"}

    def post(*args, **kwargs):
        calls.append("post")
        return Accepted()

    def get(url, **kwargs):
        calls.append(url)
        return _Response()

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr("newbee_notebook.infrastructure.document_processing.converters.mineru_local_converter.time.sleep", lambda _: None)
    converter = MinerULocalConverter(api_version="v1", base_url="http://localhost:8001")
    assert converter._post_v1_and_wait({}, []).status_code == 200
    assert calls == ["post", "http://localhost:8001/v1/tasks/job-1/result"]


def test_v1_invalid_job_id_is_rejected(monkeypatch):
    class Accepted(_Response):
        status_code = 202

        def json(self):
            return {"task_id": "../bad"}

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: Accepted())
    with pytest.raises(RuntimeError, match="invalid task ID"):
        MinerULocalConverter(api_version="v1")._post_v1_and_wait({}, [])


def test_v1_interrupted_zip_cleans_up_without_resubmitting_job(monkeypatch, tmp_path):
    from unittest.mock import Mock

    class Accepted(_Response):
        status_code = 202

        def json(self):
            return {"task_id": "job-1"}

    class BrokenZip(_Response):
        def iter_content(self, chunk_size):
            yield b"partial zip"
            raise requests.ConnectionError("interrupted download")

    post = Mock(return_value=Accepted())
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: BrokenZip())
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    monkeypatch.setattr("newbee_notebook.infrastructure.document_processing.converters.mineru_local_converter.time.sleep", lambda _: None)
    path = tmp_path / "sample.png"
    path.write_bytes(b"input")
    converter = MinerULocalConverter(api_version="v1", retry_backoff_seconds=0)
    with pytest.raises(RuntimeError, match="already submitted"):
        asyncio.run(converter.convert(str(path)))
    assert post.call_count == 1
    assert not list(tmp_path.glob("mineru_local_*.zip"))

