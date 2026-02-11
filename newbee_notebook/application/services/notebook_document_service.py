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
from newbee_notebook.infrastructure.tasks.document_tasks import process_document_task


logger = logging.getLogger(__name__)


class NotebookNotFoundError(Exception):
    """Notebook not found."""


@dataclass
class AddDocumentError:
    document_id: str
    reason: str


@dataclass
class AddDocumentResult:
    notebook_id: str
    added: List[Document]
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

            if document.status in {
                DocumentStatus.UPLOADED,
                DocumentStatus.FAILED,
            }:
                await self._document_repo.update_status(
                    document_id,
                    status=DocumentStatus.PENDING,
                    error_message=None,
                    processing_stage="queued",
                    processing_meta={"queued_by": "notebook_association"},
                )
                # Commit pending before enqueue to avoid race with worker claim.
                await self._document_repo.commit()
                self._enqueue_processing(document_id)

            # Return latest status from DB if it changed.
            current = await self._document_repo.get(document_id)
            if current:
                added.append(current)

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

    def _enqueue_processing(self, document_id: str) -> None:
        """Dispatch processing task for uploaded/failed documents."""
        if os.getenv("PROCESS_UPLOAD_SYNC", "").lower() in {"1", "true", "yes", "on"}:
            from newbee_notebook.infrastructure.tasks.document_tasks import _process_document_async

            asyncio.create_task(_process_document_async(document_id))
            return

        try:
            process_document_task.delay(document_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Celery enqueue failed for %s; running inline. error=%s", document_id, exc)
            from newbee_notebook.infrastructure.tasks.document_tasks import _process_document_async

            asyncio.create_task(_process_document_async(document_id))
