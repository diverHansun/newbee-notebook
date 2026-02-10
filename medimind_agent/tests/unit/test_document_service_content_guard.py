"""Tests for document content guard behavior."""

import asyncio
from unittest.mock import AsyncMock

from medimind_agent.application.services.document_service import DocumentService
from medimind_agent.domain.entities.document import Document
from medimind_agent.domain.value_objects.document_status import DocumentStatus
from medimind_agent.exceptions import DocumentProcessingError


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
