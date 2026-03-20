"""
Newbee Notebook - Document Service

Library-first document lifecycle:
- Upload to Library (status=uploaded)
- Add to Notebook triggers processing
- Delete performs full cleanup
"""

from typing import Optional, Tuple, List
import logging
import os
import asyncio
import re
from pathlib import PurePosixPath

from fastapi import UploadFile

from newbee_notebook.domain.entities.document import Document
from newbee_notebook.domain.entities.base import generate_uuid
from newbee_notebook.domain.repositories.diagram_repository import DiagramRepository
from newbee_notebook.domain.repositories.document_repository import DocumentRepository
from newbee_notebook.domain.repositories.library_repository import LibraryRepository
from newbee_notebook.domain.repositories.notebook_repository import NotebookRepository
from newbee_notebook.domain.repositories.reference_repository import (
    NotebookDocumentRefRepository,
    ReferenceRepository,
)
from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.domain.value_objects.document_type import DocumentType
from newbee_notebook.domain.value_objects.processing_stage import ProcessingStage
from newbee_notebook.infrastructure.storage import get_runtime_storage_backend
from newbee_notebook.infrastructure.storage.base import StorageBackend
from newbee_notebook.infrastructure.storage.object_keys import build_storage_key_candidates
from newbee_notebook.infrastructure.tasks.document_tasks import process_document_task
from newbee_notebook.infrastructure.storage.local_storage import (
    save_upload_file_with_storage,
    _decode_filename,
)
from newbee_notebook.core.common.config import get_documents_directory
from newbee_notebook.exceptions import DocumentProcessingError


logger = logging.getLogger(__name__)
ASSET_API_URL_PATTERN = re.compile(
    r"/api/v1/documents/(?P<doc_id>[^/\s)]+)/assets/(?P<asset_path>[^)\s\"'>]+)"
)


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
        diagram_repo: Optional[DiagramRepository] = None,
    ):
        self._document_repo = document_repo
        self._library_repo = library_repo
        self._notebook_repo = notebook_repo
        self._ref_repo = ref_repo
        self._reference_repo = reference_repo
        self._diagram_repo = diagram_repo

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
            await self._document_repo.update_status(
                created.document_id,
                status=DocumentStatus.PENDING,
                error_message=None,
                processing_stage=ProcessingStage.QUEUED.value,
                processing_meta={"queued_by": "auto_process"},
            )
            await self._document_repo.commit()
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
                file_path, size, ext = await save_upload_file_with_storage(
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
            from newbee_notebook.infrastructure.tasks.document_tasks import _process_document_async

            asyncio.create_task(_process_document_async(document_id))
            return

        try:
            process_document_task.delay(document_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Celery enqueue failed; running inline. error=%s", exc)
            from newbee_notebook.infrastructure.tasks.document_tasks import _process_document_async

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
    async def delete_document(self, document_id: str) -> bool:
        """Soft delete: remove index/DB data but keep on-disk document artifacts."""
        doc = await self._document_repo.get(document_id)
        if not doc:
            raise ValueError(f"Document not found: {document_id}")

        refs = await self._ref_repo.list_by_document(document_id)

        # Preserve chat references before deletion.
        try:
            await self._reference_repo.mark_source_deleted(
                document_id=document_id,
                document_title=doc.title,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("mark_source_deleted failed for %s: %s", document_id, exc)

        if refs:
            if self._diagram_repo is not None:
                await self._detach_document_from_diagrams(document_id, refs)
            await self._ref_repo.delete_by_document(document_id)
            for ref in refs:
                await self._notebook_repo.increment_document_count(ref.notebook_id, -1)

        # Delete vector/ES nodes asynchronously.
        from newbee_notebook.infrastructure.tasks.document_tasks import delete_document_nodes_task

        delete_document_nodes_task.delay(document_id)

        return await self._document_repo.delete(document_id)

    async def force_delete_document(self, document_id: str) -> bool:
        """Hard delete: soft delete plus runtime storage cleanup."""
        deleted = await self.delete_document(document_id)
        if deleted:
            storage = get_runtime_storage_backend()
            await storage.delete_prefix(f"{document_id}/")
        return deleted

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
        if doc.status in {
            DocumentStatus.UPLOADED,
            DocumentStatus.PENDING,
            DocumentStatus.PROCESSING,
        }:
            raise DocumentProcessingError(
                message="Document is still processing",
                details={
                    "document_id": document_id,
                    "status": doc.status.value,
                    "processing_stage": doc.processing_stage,
                    "stage_updated_at": doc.stage_updated_at.isoformat() if doc.stage_updated_at else None,
                    "retryable": True,
                },
            )
        if doc.status == DocumentStatus.FAILED:
            raise RuntimeError("Document processing failed")
        if doc.status not in {DocumentStatus.CONVERTED, DocumentStatus.COMPLETED}:
            raise RuntimeError("Document not processed yet")

        storage = get_runtime_storage_backend()
        resolved_content_path = await self._resolve_content_storage_key(doc, storage)
        content = await storage.get_text(resolved_content_path)
        content = await self._rewrite_asset_urls_for_remote(content, storage)

        # Self-heal legacy rows where content key/path exists but content_path was not persisted.
        if doc.content_path != resolved_content_path:
            await self._document_repo.update_status(
                document_id=document_id,
                status=doc.status,
                content_path=resolved_content_path,
                content_format=doc.content_format or "markdown",
            )
            await self._document_repo.commit()
            doc.content_path = resolved_content_path

        if format == "markdown":
            return doc, content
        if format == "text":
            return doc, _markdown_to_text(content)
        raise ValueError("Unsupported format")

    async def get_download_url(self, document_id: str) -> Optional[str]:
        """Get presigned download URL from runtime storage."""
        doc = await self._document_repo.get(document_id)
        if not doc:
            raise ValueError("Document not found")

        storage = get_runtime_storage_backend()
        candidates = self._build_storage_key_candidates(doc.file_path)
        object_key = await self._resolve_existing_storage_key(storage, candidates)
        if not object_key:
            raise FileNotFoundError("Original file not found in storage")
        return await storage.get_file_url(object_key)

    async def get_asset_url(self, document_id: str, asset_path: str) -> Optional[str]:
        """Get presigned asset URL from runtime storage."""
        doc = await self._document_repo.get(document_id)
        if not doc:
            raise ValueError("Document not found")

        storage = get_runtime_storage_backend()
        normalized = self._validate_asset_path(asset_path)
        object_key = f"{document_id}/assets/{normalized.as_posix()}"
        if not await storage.exists(object_key):
            raise FileNotFoundError("Asset file not found in storage")
        return await storage.get_file_url(object_key)

    def _validate_asset_path(self, asset_path: str) -> PurePosixPath:
        normalized = PurePosixPath((asset_path or "").replace("\\", "/"))
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError("Invalid asset path")
        return normalized

    async def _resolve_content_storage_key(self, doc: Document, storage: StorageBackend) -> str:
        candidates = self._build_storage_key_candidates(
            raw_path=doc.content_path,
            default_key=f"{doc.document_id}/markdown/content.md",
        )
        object_key = await self._resolve_existing_storage_key(storage, candidates)
        if object_key:
            return object_key
        raise FileNotFoundError("Content file not found in storage")

    async def _resolve_existing_storage_key(
        self,
        storage: StorageBackend,
        candidates: list[str],
    ) -> Optional[str]:
        for candidate in candidates:
            if await storage.exists(candidate):
                return candidate
        return None

    def _build_storage_key_candidates(
        self,
        raw_path: Optional[str],
        default_key: Optional[str] = None,
    ) -> list[str]:
        return build_storage_key_candidates(
            raw_path=raw_path,
            default_key=default_key,
            documents_root=get_documents_directory(),
        )

    async def _rewrite_asset_urls_for_remote(self, content: str, storage: StorageBackend) -> str:
        matches = list(ASSET_API_URL_PATTERN.finditer(content))
        if not matches:
            return content

        signed_urls: dict[str, str] = {}
        for match in matches:
            doc_id = match.group("doc_id")
            asset_path = match.group("asset_path").lstrip("/")
            object_key = f"{doc_id}/assets/{asset_path}"
            if object_key in signed_urls:
                continue

            if not await storage.exists(object_key):
                continue
            try:
                signed_urls[object_key] = await storage.get_file_url(object_key)
            except FileNotFoundError:
                continue

        if not signed_urls:
            return content

        def _replace(match: re.Match[str]) -> str:
            doc_id = match.group("doc_id")
            asset_path = match.group("asset_path").lstrip("/")
            object_key = f"{doc_id}/assets/{asset_path}"
            return signed_urls.get(object_key, match.group(0))

        return ASSET_API_URL_PATTERN.sub(_replace, content)

    async def _detach_document_from_diagrams(self, document_id: str, refs) -> None:
        notebook_ids = {ref.notebook_id for ref in refs}
        for notebook_id in notebook_ids:
            diagrams = await self._diagram_repo.list_by_notebook(
                notebook_id=notebook_id,
                document_id=document_id,
            )
            for diagram in diagrams:
                diagram.document_ids = [
                    current_document_id
                    for current_document_id in diagram.document_ids
                    if current_document_id != document_id
                ]
                diagram.touch()
                await self._diagram_repo.update(diagram)


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
