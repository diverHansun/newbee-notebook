import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile

from newbee_notebook.infrastructure.storage.local_storage import save_upload_file_with_storage
from newbee_notebook.infrastructure.document_processing.store import save_markdown_with_storage


class _FakeRemoteStorageBackend:
    def __init__(self) -> None:
        self.save_file_calls: list[tuple[str, bytes, str]] = []
        self.save_from_path_calls: list[tuple[str, str, str]] = []

    async def save_file(self, object_key: str, data, content_type: str = "application/octet-stream") -> str:
        self.save_file_calls.append((object_key, data.read(), content_type))
        return object_key

    async def save_from_path(self, object_key: str, local_path: str, content_type: str = "application/octet-stream") -> str:
        self.save_from_path_calls.append((object_key, local_path, content_type))
        return object_key


def test_upload_file_syncs_original_file_to_remote_storage(tmp_path: Path, monkeypatch):
    backend = _FakeRemoteStorageBackend()
    monkeypatch.setattr(
        "newbee_notebook.infrastructure.storage.local_storage.get_runtime_storage_backend",
        lambda: backend,
        raising=False,
    )

    upload = UploadFile(filename="demo.pdf", file=BytesIO(b"%PDF-sample"))

    async def _run():
        rel_path, size, ext = await save_upload_file_with_storage(
            upload,
            document_id="doc-sync-1",
            base_root=str(tmp_path),
        )

        assert rel_path == "doc-sync-1/original/demo.pdf"
        assert size == len(b"%PDF-sample")
        assert ext == "pdf"
        assert (tmp_path / rel_path).exists() is False

    asyncio.run(_run())

    assert len(backend.save_file_calls) == 1
    object_key, payload, content_type = backend.save_file_calls[0]
    assert object_key == "doc-sync-1/original/demo.pdf"
    assert payload == b"%PDF-sample"
    assert content_type == "application/pdf"
    assert backend.save_from_path_calls == []


def test_save_markdown_syncs_markdown_and_assets_to_remote_storage(tmp_path: Path, monkeypatch):
    backend = _FakeRemoteStorageBackend()
    monkeypatch.setattr(
        "newbee_notebook.infrastructure.document_processing.store.get_runtime_storage_backend",
        lambda: backend,
        raising=False,
    )

    async def _run():
        rel_path, content_size = await save_markdown_with_storage(
            document_id="doc-sync-2",
            markdown="# Title\n\n![img](images/demo.jpg)\n",
            image_assets={"images/demo.jpg": b"image-bytes"},
            metadata_assets={"layout.json": b'{"pdf_info":[1]}'},
            base_root=str(tmp_path),
        )
        assert rel_path == "doc-sync-2/markdown/content.md"
        assert content_size > 0
        assert not any(tmp_path.rglob("*"))

    asyncio.run(_run())

    object_keys = {item[0] for item in backend.save_file_calls}
    assert "doc-sync-2/markdown/content.md" in object_keys
    assert "doc-sync-2/assets/images/demo.jpg" in object_keys
    assert "doc-sync-2/assets/meta/layout.json" in object_keys
    uploaded = {item[0]: item[1] for item in backend.save_file_calls}
    assert uploaded["doc-sync-2/markdown/content.md"].decode("utf-8") == (
        "# Title\n\n![img](/api/v1/documents/doc-sync-2/assets/images/demo.jpg)\n"
    )
    assert uploaded["doc-sync-2/assets/images/demo.jpg"] == b"image-bytes"
    assert uploaded["doc-sync-2/assets/meta/layout.json"] == b'{"pdf_info":[1]}'
    assert backend.save_from_path_calls == []


@pytest.mark.parametrize(
    ("filename", "payload", "expected_content_type"),
    [
        ("demo.pptx", b"PK\x03\x04pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ("demo.epub", b"PK\x03\x04epub", "application/epub+zip"),
    ],
)
def test_upload_file_with_storage_accepts_pptx_and_epub(
    tmp_path: Path,
    monkeypatch,
    filename: str,
    payload: bytes,
    expected_content_type: str,
):
    backend = _FakeRemoteStorageBackend()
    monkeypatch.setattr(
        "newbee_notebook.infrastructure.storage.local_storage.get_runtime_storage_backend",
        lambda: backend,
        raising=False,
    )

    upload = UploadFile(filename=filename, file=BytesIO(payload))

    async def _run():
        rel_path, size, ext = await save_upload_file_with_storage(
            upload,
            document_id="doc-sync-3",
            base_root=str(tmp_path),
        )

        assert rel_path == f"doc-sync-3/original/{filename}"
        assert size == len(payload)
        assert ext == filename.rsplit(".", 1)[1]
        assert (tmp_path / rel_path).exists() is False

    asyncio.run(_run())

    assert len(backend.save_file_calls) == 1
    object_key, uploaded_payload, content_type = backend.save_file_calls[0]
    assert object_key == f"doc-sync-3/original/{filename}"
    assert uploaded_payload == payload
    assert content_type == expected_content_type
