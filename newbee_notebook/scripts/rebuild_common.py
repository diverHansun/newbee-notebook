"""Shared helpers for runtime-backed index rebuild scripts."""

from __future__ import annotations

from newbee_notebook.domain.entities.document import Document
from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.infrastructure.persistence.database import close_database, get_database
from newbee_notebook.infrastructure.persistence.repositories.document_repo_impl import (
    DocumentRepositoryImpl,
)
from newbee_notebook.infrastructure.tasks import document_tasks


async def get_rebuildable_documents(
    document_ids: list[str] | None = None,
    page_size: int = 200,
) -> list[Document]:
    """Return library documents whose markdown content should be re-indexed."""
    db = await get_database()
    try:
        async with db.session() as session:
            repo = DocumentRepositoryImpl(session)
            docs = await document_tasks._find_documents_by_status(
                doc_repo=repo,
                statuses=[DocumentStatus.CONVERTED, DocumentStatus.COMPLETED],
                document_ids=document_ids,
                page_size=page_size,
            )
            return [doc for doc in docs if doc.content_path]
    finally:
        await close_database()


async def load_document_nodes(
    document: Document,
    *,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
):
    """Load and split one converted markdown document from runtime storage."""
    if not document.content_path:
        raise RuntimeError(
            f"Document {document.document_id} has no content_path and cannot be rebuilt"
        )
    return await document_tasks._load_markdown_nodes(
        document,
        document.content_path,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
