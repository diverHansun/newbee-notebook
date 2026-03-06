import asyncio
from unittest.mock import AsyncMock

import pytest

from newbee_notebook.application.services.document_service import DocumentService
from newbee_notebook.domain.entities.document import Document
from newbee_notebook.domain.value_objects.document_status import DocumentStatus


class _FakeRemoteStorageBackend:
    def __init__(self, *, existing: set[str], texts: dict[str, str], urls: dict[str, str]) -> None:
        self._existing = existing
        self._texts = texts
        self._urls = urls
        self.url_calls: list[str] = []

    async def exists(self, object_key: str) -> bool:
        return object_key in self._existing

    async def get_text(self, object_key: str, encoding: str = "utf-8") -> str:
        if object_key not in self._texts:
            raise FileNotFoundError(object_key)
        return self._texts[object_key]

    async def get_file_url(self, object_key: str):
        self.url_calls.append(object_key)
        if object_key not in self._urls:
            raise FileNotFoundError(object_key)
        return self._urls[object_key]


def _build_service(doc_repo: AsyncMock) -> DocumentService:
    return DocumentService(
        document_repo=doc_repo,
        library_repo=AsyncMock(),
        notebook_repo=AsyncMock(),
        ref_repo=AsyncMock(),
        reference_repo=AsyncMock(),
    )


def test_get_document_content_reads_from_remote_storage(monkeypatch):
    doc_repo = AsyncMock()
    doc_repo.get = AsyncMock(
        return_value=Document(
            document_id="doc-r-1",
            title="remote-md",
            status=DocumentStatus.CONVERTED,
            content_path="doc-r-1/markdown/content.md",
        )
    )
    doc_repo.update_status = AsyncMock()
    doc_repo.commit = AsyncMock()

    backend = _FakeRemoteStorageBackend(
        existing={"doc-r-1/markdown/content.md"},
        texts={"doc-r-1/markdown/content.md": "# Remote"},
        urls={},
    )
    monkeypatch.setattr(
        "newbee_notebook.application.services.document_service.get_storage_backend",
        lambda: backend,
    )

    service = _build_service(doc_repo)

    async def _run():
        _, content = await service.get_document_content("doc-r-1", format="markdown")
        assert content == "# Remote"

    asyncio.run(_run())
    doc_repo.update_status.assert_not_awaited()


def test_get_document_content_repairs_legacy_documents_prefix_for_remote(monkeypatch):
    doc_repo = AsyncMock()
    doc_repo.get = AsyncMock(
        return_value=Document(
            document_id="doc-r-2",
            title="legacy-path",
            status=DocumentStatus.COMPLETED,
            content_path="documents/doc-r-2/markdown/content.md",
        )
    )
    doc_repo.update_status = AsyncMock()
    doc_repo.commit = AsyncMock()

    backend = _FakeRemoteStorageBackend(
        existing={"doc-r-2/markdown/content.md"},
        texts={"doc-r-2/markdown/content.md": "# Remote Legacy"},
        urls={},
    )
    monkeypatch.setattr(
        "newbee_notebook.application.services.document_service.get_storage_backend",
        lambda: backend,
    )

    service = _build_service(doc_repo)

    async def _run():
        _, content = await service.get_document_content("doc-r-2", format="markdown")
        assert content == "# Remote Legacy"

    asyncio.run(_run())
    doc_repo.update_status.assert_awaited_once()
    call_kwargs = doc_repo.update_status.await_args.kwargs
    assert call_kwargs["content_path"] == "doc-r-2/markdown/content.md"


def test_get_document_content_rewrites_asset_urls_for_remote_storage(monkeypatch):
    doc_repo = AsyncMock()
    doc_repo.get = AsyncMock(
        return_value=Document(
            document_id="doc-r-5",
            title="remote-images",
            status=DocumentStatus.COMPLETED,
            content_path="doc-r-5/markdown/content.md",
        )
    )
    doc_repo.update_status = AsyncMock()
    doc_repo.commit = AsyncMock()

    raw_md = (
        "para\\n"
        "![](/api/v1/documents/doc-r-5/assets/images/a.jpg)\\n"
        "![](/api/v1/documents/doc-r-5/assets/images/a.jpg)\\n"
        "![](/api/v1/documents/doc-r-5/assets/images/b.jpg)"
    )
    backend = _FakeRemoteStorageBackend(
        existing={
            "doc-r-5/markdown/content.md",
            "doc-r-5/assets/images/a.jpg",
            "doc-r-5/assets/images/b.jpg",
        },
        texts={"doc-r-5/markdown/content.md": raw_md},
        urls={
            "doc-r-5/assets/images/a.jpg": "http://localhost:9000/signed/a.jpg",
            "doc-r-5/assets/images/b.jpg": "http://localhost:9000/signed/b.jpg",
        },
    )
    monkeypatch.setattr(
        "newbee_notebook.application.services.document_service.get_storage_backend",
        lambda: backend,
    )

    service = _build_service(doc_repo)

    async def _run():
        _, content = await service.get_document_content("doc-r-5", format="markdown")
        assert "http://localhost:9000/signed/a.jpg" in content
        assert "http://localhost:9000/signed/b.jpg" in content
        assert "/api/v1/documents/doc-r-5/assets/images/a.jpg" not in content
        assert backend.url_calls.count("doc-r-5/assets/images/a.jpg") == 1
        assert backend.url_calls.count("doc-r-5/assets/images/b.jpg") == 1

    asyncio.run(_run())


def test_get_download_url_returns_presigned_url_for_remote_storage(monkeypatch):
    doc_repo = AsyncMock()
    doc_repo.get = AsyncMock(
        return_value=Document(
            document_id="doc-r-3",
            title="demo.pdf",
            status=DocumentStatus.UPLOADED,
            file_path="doc-r-3/original/demo.pdf",
        )
    )

    backend = _FakeRemoteStorageBackend(
        existing={"doc-r-3/original/demo.pdf"},
        texts={},
        urls={"doc-r-3/original/demo.pdf": "http://localhost:9000/download-signed"},
    )
    monkeypatch.setattr(
        "newbee_notebook.application.services.document_service.get_storage_backend",
        lambda: backend,
    )

    service = _build_service(doc_repo)

    async def _run():
        url = await service.get_download_url("doc-r-3")
        assert url == "http://localhost:9000/download-signed"

    asyncio.run(_run())


def test_get_asset_url_rejects_path_traversal_for_remote_storage(monkeypatch):
    doc_repo = AsyncMock()
    doc_repo.get = AsyncMock(
        return_value=Document(
            document_id="doc-r-4",
            title="asset",
            status=DocumentStatus.COMPLETED,
        )
    )

    backend = _FakeRemoteStorageBackend(existing=set(), texts={}, urls={})
    monkeypatch.setattr(
        "newbee_notebook.application.services.document_service.get_storage_backend",
        lambda: backend,
    )
    service = _build_service(doc_repo)

    async def _run():
        with pytest.raises(ValueError):
            await service.get_asset_url("doc-r-4", "../images/demo.jpg")

    asyncio.run(_run())
