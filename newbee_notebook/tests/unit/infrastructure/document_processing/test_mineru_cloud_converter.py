import requests

from newbee_notebook.infrastructure.document_processing.converters.mineru_cloud_converter import (
    MinerUCloudConverter,
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

