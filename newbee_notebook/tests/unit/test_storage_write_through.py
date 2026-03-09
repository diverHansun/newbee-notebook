import asyncio
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile

from newbee_notebook.infrastructure.storage.local_storage import save_upload_file_with_storage
from newbee_notebook.infrastructure.document_processing.store import save_markdown_with_storage


class _FakeRemoteStorageBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def save_from_path(self, object_key: str, local_path: str, content_type: str = "application/octet-stream") -> str:
        self.calls.append((object_key, local_path, content_type))
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
        assert (tmp_path / rel_path).exists()

    asyncio.run(_run())

    assert len(backend.calls) == 1
    object_key, local_path, content_type = backend.calls[0]
    assert object_key == "doc-sync-1/original/demo.pdf"
    assert local_path.endswith("doc-sync-1\\original\\demo.pdf") or local_path.endswith("doc-sync-1/original/demo.pdf")
    assert content_type == "application/pdf"


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

    asyncio.run(_run())

    object_keys = {item[0] for item in backend.calls}
    assert "doc-sync-2/markdown/content.md" in object_keys
    assert "doc-sync-2/assets/images/demo.jpg" in object_keys
    assert "doc-sync-2/assets/meta/layout.json" in object_keys
