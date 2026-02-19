from unittest.mock import AsyncMock

from newbee_notebook.application.services.notebook_document_service import NotebookDocumentService
from newbee_notebook.domain.entities.document import Document
from newbee_notebook.domain.value_objects.document_status import DocumentStatus


def _service() -> NotebookDocumentService:
    return NotebookDocumentService(
        notebook_repo=AsyncMock(),
        document_repo=AsyncMock(),
        ref_repo=AsyncMock(),
    )


def test_determine_processing_action_matrix():
    service = _service()

    completed = Document(
        document_id="doc-completed",
        library_id="lib-1",
        status=DocumentStatus.COMPLETED,
        content_path="documents/doc-completed/markdown/content.md",
    )
    assert service._determine_processing_action(completed) == ("none", None, False)

    pending = Document(
        document_id="doc-pending",
        library_id="lib-1",
        status=DocumentStatus.PENDING,
    )
    assert service._determine_processing_action(pending) == ("none", None, False)

    processing = Document(
        document_id="doc-processing",
        library_id="lib-1",
        status=DocumentStatus.PROCESSING,
    )
    assert service._determine_processing_action(processing) == ("none", None, False)

    converted = Document(
        document_id="doc-converted",
        library_id="lib-1",
        status=DocumentStatus.CONVERTED,
        content_path="documents/doc-converted/markdown/content.md",
    )
    assert service._determine_processing_action(converted) == ("index_only", "index_document", False)

    failed_with_content = Document(
        document_id="doc-failed-content",
        library_id="lib-1",
        status=DocumentStatus.FAILED,
        content_path="documents/doc-failed-content/markdown/content.md",
    )
    assert service._determine_processing_action(failed_with_content) == (
        "index_only",
        "index_document",
        True,
    )

    failed_without_content = Document(
        document_id="doc-failed-empty",
        library_id="lib-1",
        status=DocumentStatus.FAILED,
        content_path=None,
    )
    assert service._determine_processing_action(failed_without_content) == (
        "full_pipeline",
        "process_document",
        False,
    )

    uploaded = Document(
        document_id="doc-uploaded",
        library_id="lib-1",
        status=DocumentStatus.UPLOADED,
    )
    assert service._determine_processing_action(uploaded) == ("full_pipeline", "process_document", False)

