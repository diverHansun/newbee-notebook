"""Notebook-document association service.

Library-first workflow:
- Documents are uploaded to Library
- Notebook only associates existing Library documents
- Processing is triggered on first association when needed
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime
import asyncio
import logging
import os

from newbee_notebook.domain.entities.document import Document
from newbee_notebook.domain.entities.reference import NotebookDocumentRef
from newbee_notebook.domain.repositories.document_repository import DocumentRepository
from newbee_notebook.domain.repositories.notebook_repository import NotebookRepository
from newbee_notebook.domain.repositories.reference_repository import NotebookDocumentRefRepository
from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.domain.value_objects.processing_stage import ProcessingStage
from newbee_notebook.infrastructure.tasks.document_tasks import (
    index_document_task,
    process_document_task,
)


logger = logging.getLogger(__name__)


class NotebookNotFoundError(Exception):
    """Notebook not found."""


@dataclass
class AddDocumentError:
    document_id: str
    reason: str


@dataclass
class AddedDocument:
    document: Document
    action: str


@dataclass
class AddDocumentResult:
    notebook_id: str
    added: List[AddedDocument]
    skipped: List[AddDocumentError]
    failed: List[AddDocumentError]


class NotebookDocumentService:
    """Service for notebook-document association lifecycle."""

    def __init__(
        self,
        notebook_repo: NotebookRepository,
        document_repo: DocumentRepository,
        ref_repo: NotebookDocumentRefRepository,
    ):
        self._notebook_repo = notebook_repo
        self._document_repo = document_repo
        self._ref_repo = ref_repo

    async def add_documents(
        self,
        notebook_id: str,
        document_ids: List[str],
    ) -> AddDocumentResult:
        notebook = await self._notebook_repo.get(notebook_id)
        if not notebook:
            raise NotebookNotFoundError(f"Notebook not found: {notebook_id}")

        added: List[Document] = []
        skipped: List[AddDocumentError] = []
        failed: List[AddDocumentError] = []

        for document_id in document_ids:
            document = await self._document_repo.get(document_id)
            if not document:
                failed.append(AddDocumentError(document_id=document_id, reason="document_not_found"))
                continue
            if not document.is_library_document:
                failed.append(AddDocumentError(document_id=document_id, reason="not_library_document"))
                continue

            existing = await self._ref_repo.get_by_notebook_and_document(notebook_id, document_id)
            if existing:
                skipped.append(AddDocumentError(document_id=document_id, reason="already_added"))
                continue

            try:
                ref = NotebookDocumentRef(notebook_id=notebook_id, document_id=document_id)
                await self._ref_repo.create(ref)
                await self._notebook_repo.increment_document_count(notebook_id, 1)
            except Exception as exc:  # noqa: BLE001
                failed.append(AddDocumentError(document_id=document_id, reason=f"create_relation_failed:{exc}"))
                continue

            action, task_name, force = self._determine_processing_action(document)
            if task_name is not None:
                queued_status = self._get_queued_status_for_task(task_name)
                await self._document_repo.update_status(
                    document_id=document_id,
                    status=queued_status,
                    error_message=None,
                    processing_stage=ProcessingStage.QUEUED.value,
                    processing_meta={
                        "queued_by": "notebook_add",
                        "action": action,
                        "task_name": task_name,
                        "force": force,
                    },
                )
                await self._document_repo.commit()
                self._enqueue_processing(document_id=document_id, task_name=task_name, force=force)

            # Return latest status from DB if it changed.
            current = await self._document_repo.get(document_id)
            if current:
                added.append(AddedDocument(document=current, action=action))

        return AddDocumentResult(
            notebook_id=notebook_id,
            added=added,
            skipped=skipped,
            failed=failed,
        )

    async def list_documents(
        self,
        notebook_id: str,
        limit: int = 20,
        offset: int = 0,
        status: Optional[DocumentStatus] = None,
    ) -> Tuple[List[Tuple[Document, datetime]], int]:
        notebook = await self._notebook_repo.get(notebook_id)
        if not notebook:
            raise NotebookNotFoundError(f"Notebook not found: {notebook_id}")

        refs = await self._ref_repo.list_by_notebook(notebook_id)
        if not refs:
            return [], 0

        all_doc_ids = [r.document_id for r in refs]
        all_docs = await self._document_repo.get_batch(all_doc_ids)
        doc_map = {d.document_id: d for d in all_docs}

        filtered: List[Tuple[Document, datetime]] = []
        for ref in refs:
            doc = doc_map.get(ref.document_id)
            if not doc:
                continue
            if status and doc.status != status:
                continue
            filtered.append((doc, ref.created_at))

        total = len(filtered)
        page = filtered[offset: offset + limit]
        return page, total

    async def remove_document(self, notebook_id: str, document_id: str) -> None:
        notebook = await self._notebook_repo.get(notebook_id)
        if not notebook:
            raise NotebookNotFoundError(f"Notebook not found: {notebook_id}")

        ref = await self._ref_repo.get_by_notebook_and_document(notebook_id, document_id)
        if not ref:
            raise ValueError("notebook_document_relation_not_found")

        await self._ref_repo.delete(ref.reference_id)
        await self._notebook_repo.increment_document_count(notebook_id, -1)

    @staticmethod
    def _determine_processing_action(document: Document) -> tuple[str, str | None, bool]:
        """Return (action, task_name, force) for notebook association."""
        if document.status in {DocumentStatus.COMPLETED, DocumentStatus.PENDING, DocumentStatus.PROCESSING}:
            return "none", None, False

        if document.status == DocumentStatus.CONVERTED:
            return "index_only", "index_document", False

        if document.status == DocumentStatus.FAILED and document.content_path:
            return "index_only", "index_document", True

        return "full_pipeline", "process_document", False

    @staticmethod
    def _get_queued_status_for_task(task_name: str) -> DocumentStatus:
        if task_name == "index_document":
            return DocumentStatus.CONVERTED
        return DocumentStatus.PENDING

    def _enqueue_processing(self, document_id: str, task_name: str, force: bool = False) -> None:
        """Dispatch processing task with sync fallback for local development."""
        if os.getenv("PROCESS_UPLOAD_SYNC", "").lower() in {"1", "true", "yes", "on"}:
            from newbee_notebook.infrastructure.tasks.document_tasks import (
                _index_document_async,
                _process_document_async,
            )

            if task_name == "index_document":
                asyncio.create_task(_index_document_async(document_id, force=force))
            else:
                asyncio.create_task(_process_document_async(document_id, force=force))
            return

        try:
            if task_name == "index_document":
                index_document_task.delay(document_id, force=force)
            else:
                process_document_task.delay(document_id, force=force)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Celery enqueue failed for %s task=%s; running inline. error=%s",
                document_id,
                task_name,
                exc,
            )
            from newbee_notebook.infrastructure.tasks.document_tasks import (
                _index_document_async,
                _process_document_async,
            )

            if task_name == "index_document":
                asyncio.create_task(_index_document_async(document_id, force=force))
            else:
                asyncio.create_task(_process_document_async(document_id, force=force))
