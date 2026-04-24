import asyncio

import requests

from newbee_notebook.infrastructure.document_processing.converters.mineru_local_converter import (
    MinerULocalConverter,
)


def test_convert_range_sends_new_local_form_fields(monkeypatch, tmp_path):
    pdf_path = tmp_path / "demo.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    captured: dict[str, object] = {}

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

    def _fake_post(url, files, data, timeout, stream):  # noqa: ANN001
        captured["url"] = url
        captured["data"] = data
        captured["timeout"] = timeout
        captured["stream"] = stream
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

    result = asyncio.run(converter._convert_range(pdf_path, start_page=0, end_page=0, total_pages=1))

    assert result.markdown == "# ok"
    assert ("parse_method", "ocr") in captured["data"]
    assert ("formula_enable", "false") in captured["data"]
    assert ("table_enable", "true") in captured["data"]

