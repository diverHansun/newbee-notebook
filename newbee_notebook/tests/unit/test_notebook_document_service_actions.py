import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

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


def test_add_documents_requeues_failed_document_without_content_before_dispatch(monkeypatch):
    notebook_repo = AsyncMock()
    notebook_repo.get = AsyncMock(return_value=SimpleNamespace(notebook_id="nb-1"))
    notebook_repo.increment_document_count = AsyncMock()

    failed_doc = Document(
        document_id="doc-failed-empty",
        library_id="lib-1",
        title="failed-empty",
        status=DocumentStatus.FAILED,
        content_path=None,
        error_message="old error",
    )
    queued_doc = Document(
        document_id="doc-failed-empty",
        library_id="lib-1",
        title="failed-empty",
        status=DocumentStatus.PENDING,
        processing_stage="queued",
    )
    document_repo = AsyncMock()
    document_repo.get = AsyncMock(side_effect=[failed_doc, queued_doc])
    document_repo.update_status = AsyncMock()
    document_repo.commit = AsyncMock()

    ref_repo = AsyncMock()
    ref_repo.get_by_notebook_and_document = AsyncMock(return_value=None)
    ref_repo.create = AsyncMock()

    delay = Mock()
    monkeypatch.setattr(
        "newbee_notebook.application.services.notebook_document_service.process_document_task.delay",
        delay,
    )

    service = NotebookDocumentService(
        notebook_repo=notebook_repo,
        document_repo=document_repo,
        ref_repo=ref_repo,
    )

    result = asyncio.run(service.add_documents("nb-1", ["doc-failed-empty"]))

    document_repo.update_status.assert_awaited_once()
    kwargs = document_repo.update_status.await_args.kwargs
    assert kwargs["document_id"] == "doc-failed-empty"
    assert kwargs["status"] == DocumentStatus.PENDING
    assert kwargs["error_message"] is None
    assert kwargs["processing_stage"] == "queued"
    assert kwargs["processing_meta"]["action"] == "full_pipeline"
    document_repo.commit.assert_awaited_once()
    delay.assert_called_once_with("doc-failed-empty", force=False)
    assert result.added[0].document.status == DocumentStatus.PENDING
    assert result.added[0].action == "full_pipeline"


def test_add_documents_requeues_failed_document_with_content_as_index_only(monkeypatch):
    notebook_repo = AsyncMock()
    notebook_repo.get = AsyncMock(return_value=SimpleNamespace(notebook_id="nb-1"))
    notebook_repo.increment_document_count = AsyncMock()

    failed_doc = Document(
        document_id="doc-failed-content",
        library_id="lib-1",
        title="failed-content",
        status=DocumentStatus.FAILED,
        content_path="doc-failed-content/markdown/content.md",
        error_message="old error",
    )
    queued_doc = Document(
        document_id="doc-failed-content",
        library_id="lib-1",
        title="failed-content",
        status=DocumentStatus.CONVERTED,
        content_path="doc-failed-content/markdown/content.md",
        processing_stage="queued",
    )
    document_repo = AsyncMock()
    document_repo.get = AsyncMock(side_effect=[failed_doc, queued_doc])
    document_repo.update_status = AsyncMock()
    document_repo.commit = AsyncMock()

    ref_repo = AsyncMock()
    ref_repo.get_by_notebook_and_document = AsyncMock(return_value=None)
    ref_repo.create = AsyncMock()

    delay = Mock()
    monkeypatch.setattr(
        "newbee_notebook.application.services.notebook_document_service.index_document_task.delay",
        delay,
    )

    service = NotebookDocumentService(
        notebook_repo=notebook_repo,
        document_repo=document_repo,
        ref_repo=ref_repo,
    )

    result = asyncio.run(service.add_documents("nb-1", ["doc-failed-content"]))

    document_repo.update_status.assert_awaited_once()
    kwargs = document_repo.update_status.await_args.kwargs
    assert kwargs["document_id"] == "doc-failed-content"
    assert kwargs["status"] == DocumentStatus.CONVERTED
    assert kwargs["error_message"] is None
    assert kwargs["processing_stage"] == "queued"
    assert kwargs["processing_meta"]["action"] == "index_only"
    document_repo.commit.assert_awaited_once()
    delay.assert_called_once_with("doc-failed-content", force=True)
    assert result.added[0].document.status == DocumentStatus.CONVERTED
    assert result.added[0].action == "index_only"

