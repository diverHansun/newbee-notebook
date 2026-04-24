from pathlib import Path

from newbee_notebook.infrastructure.document_processing.cloud_batch_service import (
    CloudBatchDocument,
    MinerUCloudBatchService,
    build_cloud_batch_groups,
)
from newbee_notebook.infrastructure.document_processing.converters.mineru_cloud_converter import (
    MinerUCloudConverter,
)


def _doc(document_id: str, filename: str) -> CloudBatchDocument:
    return CloudBatchDocument(
        document_id=document_id,
        title=filename,
        local_path=Path(filename),
    )


def test_build_cloud_batch_groups_separates_html_and_default_routes():
    groups = build_cloud_batch_groups(
        [
            _doc("doc-1", "alpha.pdf"),
            _doc("doc-2", "beta.docx"),
            _doc("doc-3", "gamma.html"),
        ]
    )

    assert len(groups) == 2
    assert groups[0].route == "default"
    assert [item.document_id for item in groups[0].items] == ["doc-1", "doc-2"]
    assert groups[1].route == "html"
    assert [item.document_id for item in groups[1].items] == ["doc-3"]


def test_build_cloud_batch_groups_slices_every_fifty_documents():
    docs = [_doc(f"doc-{idx}", f"doc-{idx}.pdf") for idx in range(52)]

    groups = build_cloud_batch_groups(docs, max_batch_size=50)

    assert len(groups) == 2
    assert groups[0].route == "default"
    assert len(groups[0].items) == 50
    assert len(groups[1].items) == 2


def test_batch_service_reuses_one_batch_request_for_multiple_documents(monkeypatch, tmp_path):
    doc_one_path = tmp_path / "alpha.pdf"
    doc_two_path = tmp_path / "beta.docx"
    doc_one_path.write_bytes(b"%PDF-1.4\n")
    doc_two_path.write_bytes(b"docx")

    converter = MinerUCloudConverter(api_key="dummy-key")
    service = MinerUCloudBatchService(converter)

    captured: dict[str, object] = {}
    uploaded: list[tuple[str, str]] = []

    def _fake_request_upload_urls(file_entries, model_version=None):  # noqa: ANN001
        captured["file_entries"] = file_entries
        captured["model_version"] = model_version
        return "batch-1", ["https://upload/1", "https://upload/2"]

    def _fake_upload_file(upload_url: str, file_path: Path):
        uploaded.append((upload_url, file_path.name))

    def _fake_poll_until_done_items(batch_id: str):
        assert batch_id == "batch-1"
        return [
            {"data_id": "doc-1", "state": "done", "full_zip_url": "zip://1"},
            {"data_id": "doc-2", "state": "done", "full_zip_url": "zip://2"},
        ]

    def _fake_download_zip(full_zip_url: str) -> bytes:
        return full_zip_url.encode("utf-8")

    def _fake_parse_result_zip(zip_bytes: bytes):
        return f"# {zip_bytes.decode('utf-8')}", {}, {}, 1

    monkeypatch.setattr(converter, "_request_upload_urls", _fake_request_upload_urls)
    monkeypatch.setattr(converter, "_upload_file", _fake_upload_file)
    monkeypatch.setattr(converter, "_poll_until_done_items", _fake_poll_until_done_items)
    monkeypatch.setattr(converter, "_download_zip", _fake_download_zip)
    monkeypatch.setattr(converter, "_parse_result_zip", _fake_parse_result_zip)

    results, failures = service.convert_documents(
        [
            CloudBatchDocument(document_id="doc-1", title="alpha", local_path=doc_one_path),
            CloudBatchDocument(document_id="doc-2", title="beta", local_path=doc_two_path),
        ]
    )

    assert failures == []
    assert captured["file_entries"] == [
        {"name": "alpha.pdf", "data_id": "doc-1"},
        {"name": "beta.docx", "data_id": "doc-2"},
    ]
    assert captured["model_version"] is None
    assert uploaded == [("https://upload/1", "alpha.pdf"), ("https://upload/2", "beta.docx")]
    assert [item.document_id for item in results] == ["doc-1", "doc-2"]
    assert [item.markdown for item in results] == ["# zip://1", "# zip://2"]
