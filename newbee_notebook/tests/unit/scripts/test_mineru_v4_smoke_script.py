from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import requests


def _load_script_module():
    script_path = Path(__file__).resolve().parents[4] / "scripts" / "mineru_v4_smoke_test.py"
    spec = importlib.util.spec_from_file_location("mineru_v4_smoke_test", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load script module: {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_groups_separates_html_and_respects_batch_size(tmp_path):
    script = _load_script_module()
    files = [
        script.SmokeFile(path=tmp_path / "alpha.pdf", data_id="doc-1"),
        script.SmokeFile(path=tmp_path / "beta.docx", data_id="doc-2"),
        script.SmokeFile(path=tmp_path / "gamma.html", data_id="doc-3"),
        script.SmokeFile(path=tmp_path / "delta.htm", data_id="doc-4"),
    ]

    groups = script._build_groups(files, max_batch_size=1)

    assert [group.route for group in groups] == ["default", "default", "html", "html"]
    assert [group.files[0].data_id for group in groups] == ["doc-1", "doc-2", "doc-3", "doc-4"]


def test_request_upload_urls_includes_batch_fields(monkeypatch):
    script = _load_script_module()
    captured: dict[str, object] = {}

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "code": 0,
                "data": {
                    "batch_id": "batch-1",
                    "file_urls": ["https://upload/1", "https://upload/2"],
                },
            }

    def _fake_post(url, headers, json, timeout):  # noqa: ANN001
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(requests, "post", _fake_post)

    batch_id, upload_urls = script._request_upload_urls(
        api_base="https://mineru.net",
        api_key="dummy-key",
        user_token=None,
        file_entries=[
            {"name": "alpha.pdf", "data_id": "doc-1"},
            {"name": "beta.html", "data_id": "doc-2"},
        ],
        timeout=30.0,
        model_version="MinerU-HTML",
        enable_formula=False,
        enable_table=True,
        language="en",
        is_ocr=False,
    )

    assert batch_id == "batch-1"
    assert upload_urls == ["https://upload/1", "https://upload/2"]
    assert captured["url"] == "https://mineru.net/api/v4/file-urls/batch"
    assert captured["json"] == {
        "files": [
            {"name": "alpha.pdf", "data_id": "doc-1", "is_ocr": False},
            {"name": "beta.html", "data_id": "doc-2", "is_ocr": False},
        ],
        "model_version": "MinerU-HTML",
        "enable_formula": False,
        "enable_table": True,
        "language": "en",
    }
