"""
MediMind Agent - Document Service

Skeleton service for document registration, listing, and deletion.
Processing / chunking / embedding will be added later.
"""

from typing import Optional, Tuple, List
import logging
import os
import asyncio

from medimind_agent.domain.entities.document import Document
from medimind_agent.domain.repositories.document_repository import DocumentRepository
from medimind_agent.domain.repositories.library_repository import LibraryRepository
from medimind_agent.domain.repositories.notebook_repository import NotebookRepository
from medimind_agent.domain.repositories.reference_repository import NotebookDocumentRefRepository
from medimind_agent.domain.value_objects.document_status import DocumentStatus
from medimind_agent.domain.value_objects.document_type import DocumentType
from medimind_agent.infrastructure.tasks.document_tasks import process_document_task
from medimind_agent.infrastructure.storage.local_storage import save_upload_file
from fastapi import UploadFile
from medimind_agent.core.rag.embeddings import build_embedding
from medimind_agent.core.engine import load_pgvector_index, load_es_index
from medimind_agent.core.common.config import (
    get_storage_config,
    get_embedding_provider,
    get_pgvector_config_for_provider,
)
from medimind_agent.infrastructure.pgvector import PGVectorConfig
from medimind_agent.infrastructure.elasticsearch import ElasticsearchConfig


logger = logging.getLogger(__name__)


class DocumentOwnershipError(Exception):
    """Raised when document ownership is invalid or notebook not found."""


class DocumentService:
    """
    Application service for Document management.

    Current scope:
    - Register documents for Library or Notebook
    - List and query documents
    - Delete documents with reference checks
    Processing and indexing will be added in later tasks.
    """

    def __init__(
        self,
        document_repo: DocumentRepository,
        library_repo: LibraryRepository,
        notebook_repo: NotebookRepository,
        ref_repo: NotebookDocumentRefRepository,
    ):
        self._document_repo = document_repo
        self._library_repo = library_repo
        self._notebook_repo = notebook_repo
        self._ref_repo = ref_repo

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #
    async def create_library_document(
        self,
        title: str,
        content_type: DocumentType,
        file_path: str = "",
        url: Optional[str] = None,
        file_size: int = 0,
        auto_process: bool = True,
    ) -> Document:
        library = await self._library_repo.get_or_create()
        doc = Document(
            title=title,
            content_type=content_type,
            file_path=file_path,
            url=url,
            status=DocumentStatus.PENDING,
            library_id=library.library_id,
            file_size=file_size,
        )
        created = await self._document_repo.create(doc)
        logger.info("Created library document %s", created.document_id)

        if auto_process:
            self.enqueue_processing(created.document_id)
        return created

    async def create_notebook_document(
        self,
        notebook_id: str,
        title: str,
        content_type: DocumentType,
        file_path: str = "",
        url: Optional[str] = None,
        file_size: int = 0,
        auto_process: bool = True,
    ) -> Document:
        notebook = await self._notebook_repo.get(notebook_id)
        if not notebook:
            raise DocumentOwnershipError(f"Notebook not found: {notebook_id}")

        doc = Document(
            title=title,
            content_type=content_type,
            file_path=file_path,
            url=url,
            status=DocumentStatus.PENDING,
            notebook_id=notebook_id,
            file_size=file_size,
        )
        created = await self._document_repo.create(doc)
        logger.info("Created notebook document %s", created.document_id)

        await self._notebook_repo.increment_document_count(notebook_id, 1)

        if auto_process:
            self.enqueue_processing(created.document_id)
        return created

    async def save_upload_and_register(
        self,
        upload: UploadFile,
        to_library: bool = True,
        notebook_id: Optional[str] = None,
        base_root: Optional[str] = None,
    ) -> Document:
        """Save uploaded file, register document, and enqueue processing."""
        file_path, size, ext = save_upload_file(upload, base_root)
        title = upload.filename or "uploaded"
        content_type = DocumentType.from_extension(ext)
        if to_library:
            return await self.create_library_document(
                title=title,
                content_type=content_type,
                file_path=file_path,
                file_size=size,
                auto_process=True,
            )
        else:
            return await self.create_notebook_document(
                notebook_id=notebook_id,
                title=title,
                content_type=content_type,
                file_path=file_path,
                file_size=size,
                auto_process=True,
            )

    def enqueue_processing(self, document_id: str) -> None:
        """Dispatch async processing via Celery or sync fallback."""
        # Optional synchronous fallback for dev environments without Celery
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
            limit=limit, offset=offset, status=status
        )
        total = await self._document_repo.count_by_library(status=status)
        return docs, total

    async def list_notebook_documents(
        self,
        notebook_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Document], int]:
        notebook = await self._notebook_repo.get(notebook_id)
        if not notebook:
            raise DocumentOwnershipError(f"Notebook not found: {notebook_id}")

        docs = await self._document_repo.list_by_notebook(
            notebook_id, limit=limit, offset=offset
        )
        total = await self._document_repo.count_by_notebook(notebook_id)
        return docs, total

    # ------------------------------------------------------------------ #
    # Deletion
    # ------------------------------------------------------------------ #
    async def delete_document(self, document_id: str, force: bool = False) -> bool:
        doc = await self._document_repo.get(document_id)
        if not doc:
            raise ValueError(f"Document not found: {document_id}")

        # Check notebook references (Library document can be referenced by notebooks)
        if doc.is_library_document:
            ref_count = await self._ref_repo.count_by_document(document_id)
            if ref_count > 0 and not force:
                raise RuntimeError(
                    f"Document is referenced by {ref_count} notebook(s). "
                    f"Use force=true to delete."
                )
            if ref_count > 0:
                await self._ref_repo.delete_by_document(document_id)

        # Adjust counters
        if doc.is_notebook_document and doc.notebook_id:
            await self._notebook_repo.increment_document_count(doc.notebook_id, -1)

        result = await self._document_repo.delete(document_id)
        # async cleanup of vector/ES nodes
        from medimind_agent.infrastructure.tasks.document_tasks import delete_document_nodes_task
        delete_document_nodes_task.delay(document_id)
        return result
