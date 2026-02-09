"""
MediMind Agent - Document Service

Library-first document lifecycle:
- Upload to Library (status=uploaded)
- Add to Notebook triggers processing
- Delete performs full cleanup
"""

from typing import Optional, Tuple, List
import logging
import os
import asyncio
import shutil
from pathlib import Path
from pathlib import PurePosixPath

from fastapi import UploadFile

from medimind_agent.domain.entities.document import Document
from medimind_agent.domain.entities.base import generate_uuid
from medimind_agent.domain.repositories.document_repository import DocumentRepository
from medimind_agent.domain.repositories.library_repository import LibraryRepository
from medimind_agent.domain.repositories.notebook_repository import NotebookRepository
from medimind_agent.domain.repositories.reference_repository import (
    NotebookDocumentRefRepository,
    ReferenceRepository,
)
from medimind_agent.domain.value_objects.document_status import DocumentStatus
from medimind_agent.domain.value_objects.document_type import DocumentType
from medimind_agent.infrastructure.tasks.document_tasks import process_document_task
from medimind_agent.infrastructure.storage.local_storage import save_upload_file, _decode_filename
from medimind_agent.core.common.config import get_documents_directory


logger = logging.getLogger(__name__)


class DocumentOwnershipError(Exception):
    """Raised when document ownership is invalid or notebook not found."""


class DocumentService:
    """Application service for document lifecycle management."""

    def __init__(
        self,
        document_repo: DocumentRepository,
        library_repo: LibraryRepository,
        notebook_repo: NotebookRepository,
        ref_repo: NotebookDocumentRefRepository,
        reference_repo: ReferenceRepository,
    ):
        self._document_repo = document_repo
        self._library_repo = library_repo
        self._notebook_repo = notebook_repo
        self._ref_repo = ref_repo
        self._reference_repo = reference_repo

    # ------------------------------------------------------------------ #
    # Registration and upload
    # ------------------------------------------------------------------ #
    async def create_library_document(
        self,
        title: str,
        content_type: DocumentType,
        file_path: str = "",
        url: Optional[str] = None,
        file_size: int = 0,
        auto_process: bool = False,
    ) -> Document:
        """Create a library document record.

        This method is kept for compatibility. New upload flow should call
        upload_to_library() with files.
        """
        library = await self._library_repo.get_or_create()
        doc = Document(
            title=title,
            content_type=content_type,
            file_path=file_path,
            url=url,
            status=DocumentStatus.UPLOADED,
            library_id=library.library_id,
            file_size=file_size,
        )
        created = await self._document_repo.create(doc)
        logger.info("Created library document %s", created.document_id)

        if auto_process:
            self.enqueue_processing(created.document_id)
        return created

    async def upload_to_library(
        self,
        files: List[UploadFile],
        base_root: Optional[str] = None,
    ) -> Tuple[List[Document], List[dict]]:
        """Batch upload files to Library.

        Files are only saved and registered. No conversion/embedding is triggered.
        """
        library = await self._library_repo.get_or_create()
        documents: List[Document] = []
        failed: List[dict] = []

        for upload in files:
            try:
                document_id = generate_uuid()
                file_path, size, ext = save_upload_file(
                    upload,
                    document_id=document_id,
                    base_root=base_root,
                )
                title = _decode_filename(upload.filename or "uploaded")
                content_type = DocumentType.from_extension(ext)

                doc = Document(
                    document_id=document_id,
                    title=title,
                    content_type=content_type,
                    file_path=file_path,
                    file_size=size,
                    status=DocumentStatus.UPLOADED,
                    library_id=library.library_id,
                )
                created = await self._document_repo.create(doc)
                documents.append(created)
            except Exception as exc:  # noqa: BLE001
                failed.append(
                    {
                        "filename": upload.filename or "uploaded",
                        "reason": str(exc),
                    }
                )

        return documents, failed

    def enqueue_processing(self, document_id: str) -> None:
        """Dispatch async processing via Celery or sync fallback."""
        if os.getenv("PROCESS_UPLOAD_SYNC", "").lower() in {"1", "true", "yes", "on"}:
            from medimind_agent.infrastructure.tasks.document_tasks import _process_document_async

            asyncio.create_task(_process_document_async(document_id))
            return

        try:
            process_document_task.delay(document_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Celery enqueue failed; running inline. error=%s", exc)
            from medimind_agent.infrastructure.tasks.document_tasks import _process_document_async

            asyncio.create_task(_process_document_async(document_id))

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    async def get(self, document_id: str) -> Optional[Document]:
        return await self._document_repo.get(document_id)

    async def list_library_documents(
        self,
        limit: int = 20,
        offset: int = 0,
        status: Optional[DocumentStatus] = None,
    ) -> Tuple[List[Document], int]:
        docs = await self._document_repo.list_by_library(
            limit=limit,
            offset=offset,
            status=status,
        )
        total = await self._document_repo.count_by_library(status=status)
        return docs, total

    # ------------------------------------------------------------------ #
    # Deletion
    # ------------------------------------------------------------------ #
    async def delete_document(self, document_id: str, force: bool = False) -> bool:
        doc = await self._document_repo.get(document_id)
        if not doc:
            raise ValueError(f"Document not found: {document_id}")

        refs = await self._ref_repo.list_by_document(document_id)
        if refs and not force:
            raise RuntimeError(
                f"Document is referenced by {len(refs)} notebook(s). Use force=true to delete."
            )

        # Preserve chat references before deletion.
        try:
            await self._reference_repo.mark_source_deleted(
                document_id=document_id,
                document_title=doc.title,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("mark_source_deleted failed for %s: %s", document_id, exc)

        if refs:
            await self._ref_repo.delete_by_document(document_id)
            for ref in refs:
                await self._notebook_repo.increment_document_count(ref.notebook_id, -1)

        # Delete vector/ES nodes asynchronously.
        from medimind_agent.infrastructure.tasks.document_tasks import delete_document_nodes_task

        delete_document_nodes_task.delay(document_id)

        # Delete file system artifacts synchronously.
        await self._delete_document_files(document_id)

        return await self._document_repo.delete(document_id)

    async def _delete_document_files(self, document_id: str) -> bool:
        """Delete all files under data/documents/{document_id}."""
        doc_dir = Path(get_documents_directory()) / document_id
        if doc_dir.exists() and doc_dir.is_dir():
            shutil.rmtree(doc_dir, ignore_errors=True)
            return True
        return False

    # ------------------------------------------------------------------ #
    # Content retrieval
    # ------------------------------------------------------------------ #
    async def get_document_content(
        self,
        document_id: str,
        format: str = "markdown",
    ) -> tuple[Document, str]:
        doc = await self._document_repo.get(document_id)
        if not doc:
            raise ValueError("Document not found")
        if doc.status != DocumentStatus.COMPLETED:
            raise RuntimeError("Document not processed yet")
        if not doc.content_path:
            raise RuntimeError("Content not available for this document")

        content_path = Path(get_documents_directory()) / doc.content_path
        if not content_path.exists():
            raise FileNotFoundError("Content file not found on disk")

        content = content_path.read_text(encoding="utf-8")
        if format == "markdown":
            return doc, content
        if format == "text":
            return doc, _markdown_to_text(content)
        raise ValueError("Unsupported format")

    async def get_download_path(self, document_id: str) -> tuple[Path, str]:
        """Get original file path for download."""
        doc = await self._document_repo.get(document_id)
        if not doc:
            raise ValueError("Document not found")

        raw_path = Path(doc.file_path)
        file_path = raw_path if raw_path.is_absolute() else (Path(get_documents_directory()) / raw_path)
        if not file_path.exists():
            raise FileNotFoundError("Original file not found on disk")

        return file_path, file_path.name

    async def get_asset_path(self, document_id: str, asset_path: str) -> Path:
        """Get generated asset file path under data/documents/{document_id}/assets/."""
        doc = await self._document_repo.get(document_id)
        if not doc:
            raise ValueError("Document not found")

        normalized = PurePosixPath((asset_path or "").replace("\\", "/"))
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError("Invalid asset path")

        candidate = Path(get_documents_directory()) / document_id / "assets" / Path(*normalized.parts)
        if not candidate.exists() or not candidate.is_file():
            raise FileNotFoundError("Asset file not found on disk")
        return candidate


def _markdown_to_text(markdown: str) -> str:
    """Lightweight markdown -> plain text conversion for API use."""
    import re

    lines = []
    for line in markdown.splitlines():
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^[-*+]\s+", "", line)
        lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return text
