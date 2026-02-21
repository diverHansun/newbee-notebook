"""Tests for document content guard behavior."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from newbee_notebook.application.services.document_service import DocumentService
from newbee_notebook.domain.entities.document import Document
from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.exceptions import DocumentProcessingError


def test_get_document_content_raises_structured_processing_error():
    doc_repo = AsyncMock()
    doc_repo.get = AsyncMock(
        return_value=Document(
            document_id="doc-1",
            title="sample",
            status=DocumentStatus.PROCESSING,
            processing_stage="indexing_es",
        )
    )

    service = DocumentService(
        document_repo=doc_repo,
        library_repo=AsyncMock(),
        notebook_repo=AsyncMock(),
        ref_repo=AsyncMock(),
        reference_repo=AsyncMock(),
    )

    async def _run():
        try:
            await service.get_document_content("doc-1", format="markdown")
            raise AssertionError("DocumentProcessingError was not raised")
        except DocumentProcessingError as exc:
            assert exc.error_code == "E4001"
            assert exc.details["status"] == "processing"
            assert exc.details["processing_stage"] == "indexing_es"
            assert exc.details["retryable"] is True

    asyncio.run(_run())


def test_get_document_content_allows_converted_with_markdown_content(tmp_path: Path):
    doc_id = "doc-2"
    markdown_dir = tmp_path / doc_id / "markdown"
    markdown_dir.mkdir(parents=True, exist_ok=True)
    content_file = markdown_dir / "content.md"
    content_file.write_text("# Converted\n\nhello", encoding="utf-8")

    doc_repo = AsyncMock()
    doc_repo.get = AsyncMock(
        return_value=Document(
            document_id=doc_id,
            title="converted",
            status=DocumentStatus.CONVERTED,
            content_path=f"{doc_id}/markdown/content.md",
            processing_stage=None,
        )
    )

    service = DocumentService(
        document_repo=doc_repo,
        library_repo=AsyncMock(),
        notebook_repo=AsyncMock(),
        ref_repo=AsyncMock(),
        reference_repo=AsyncMock(),
    )

    async def _run():
        with patch("newbee_notebook.application.services.document_service.get_documents_directory", return_value=str(tmp_path)):
            _, content = await service.get_document_content(doc_id, format="markdown")
            assert "# Converted" in content

    asyncio.run(_run())


def test_get_document_content_repairs_missing_content_path_from_fallback(tmp_path: Path):
    doc_id = "doc-3"
    markdown_dir = tmp_path / doc_id / "markdown"
    markdown_dir.mkdir(parents=True, exist_ok=True)
    (markdown_dir / "content.md").write_text("# Recovered", encoding="utf-8")

    doc_repo = AsyncMock()
    doc_repo.get = AsyncMock(
        return_value=Document(
            document_id=doc_id,
            title="completed-without-path",
            status=DocumentStatus.COMPLETED,
            content_path=None,
            processing_stage=None,
        )
    )
    doc_repo.update_status = AsyncMock()
    doc_repo.commit = AsyncMock()

    service = DocumentService(
        document_repo=doc_repo,
        library_repo=AsyncMock(),
        notebook_repo=AsyncMock(),
        ref_repo=AsyncMock(),
        reference_repo=AsyncMock(),
    )

    async def _run():
        with patch("newbee_notebook.application.services.document_service.get_documents_directory", return_value=str(tmp_path)):
            _, content = await service.get_document_content(doc_id, format="markdown")
            assert "Recovered" in content

    asyncio.run(_run())

    doc_repo.update_status.assert_awaited_once()
    call_kwargs = doc_repo.update_status.await_args.kwargs
    assert call_kwargs["document_id"] == doc_id
    assert call_kwargs["status"] == DocumentStatus.COMPLETED
    assert call_kwargs["content_path"] == f"{doc_id}/markdown/content.md"
    doc_repo.commit.assert_awaited_once()
