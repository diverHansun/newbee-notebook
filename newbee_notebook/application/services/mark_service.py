"""Application service for marks."""

from typing import Optional

from newbee_notebook.domain.entities.mark import Mark
from newbee_notebook.domain.repositories.document_repository import DocumentRepository
from newbee_notebook.domain.repositories.mark_repository import MarkRepository
from newbee_notebook.domain.repositories.reference_repository import (
    NotebookDocumentRefRepository,
)
from newbee_notebook.domain.value_objects.document_status import DocumentStatus


class MarkNotFoundError(Exception):
    """Raised when a mark does not exist."""


class MarkDocumentNotFoundError(Exception):
    """Raised when the target document does not exist."""


class MarkDocumentNotReadyError(Exception):
    """Raised when the target document cannot accept marks yet."""


class MarkService:
    """CRUD-style service for document marks."""

    def __init__(
        self,
        mark_repo: MarkRepository,
        document_repo: Optional[DocumentRepository] = None,
        ref_repo: Optional[NotebookDocumentRefRepository] = None,
    ):
        self.mark_repo = mark_repo
        self.document_repo = document_repo
        self.ref_repo = ref_repo

    async def create(
        self,
        document_id: str,
        anchor_text: str,
        char_offset: int,
        context_text: Optional[str] = None,
    ) -> Mark:
        await self._ensure_document_ready(document_id)
        mark = Mark(
            document_id=document_id,
            anchor_text=anchor_text,
            char_offset=char_offset,
            context_text=context_text,
        )
        return await self.mark_repo.create(mark)

    async def get(self, mark_id: str) -> Optional[Mark]:
        return await self.mark_repo.get(mark_id)

    async def get_or_raise(self, mark_id: str) -> Mark:
        mark = await self.get(mark_id)
        if not mark:
            raise MarkNotFoundError(f"Mark not found: {mark_id}")
        return mark

    async def list_by_document(self, document_id: str) -> list[Mark]:
        return await self.mark_repo.list_by_document(document_id)

    async def list_by_notebook(
        self,
        notebook_id: str,
        document_id: Optional[str] = None,
    ) -> list[Mark]:
        if document_id:
            refs = await self._list_notebook_document_ids(notebook_id)
            if document_id not in refs:
                return []
            return await self.list_by_document(document_id)

        marks: list[Mark] = []
        for current_document_id in await self._list_notebook_document_ids(notebook_id):
            marks.extend(await self.mark_repo.list_by_document(current_document_id))
        return sorted(marks, key=lambda item: item.created_at, reverse=True)

    async def count_by_document(self, document_id: str) -> int:
        return len(await self.mark_repo.list_by_document(document_id))

    async def delete(self, mark_id: str) -> bool:
        await self.get_or_raise(mark_id)
        return await self.mark_repo.delete(mark_id)

    async def _ensure_document_ready(self, document_id: str) -> None:
        if self.document_repo is None:
            return
        document = await self.document_repo.get(document_id)
        if document is None:
            raise MarkDocumentNotFoundError(f"Document not found: {document_id}")
        if document.status not in {DocumentStatus.CONVERTED, DocumentStatus.COMPLETED}:
            raise MarkDocumentNotReadyError(
                f"Document is not ready for marks: {document_id}"
            )

    async def _list_notebook_document_ids(self, notebook_id: str) -> list[str]:
        if self.ref_repo is None:
            return []
        refs = await self.ref_repo.list_by_notebook(notebook_id)
        return [ref.document_id for ref in refs]
