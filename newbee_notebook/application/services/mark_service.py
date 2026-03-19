"""Application service for marks."""

from typing import Optional

from newbee_notebook.domain.entities.mark import Mark
from newbee_notebook.domain.repositories.mark_repository import MarkRepository


class MarkNotFoundError(Exception):
    """Raised when a mark does not exist."""


class MarkService:
    """CRUD-style service for document marks."""

    def __init__(self, mark_repo: MarkRepository):
        self.mark_repo = mark_repo

    async def create(
        self,
        document_id: str,
        anchor_text: str,
        char_offset: int,
        context_text: Optional[str] = None,
    ) -> Mark:
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

    async def delete(self, mark_id: str) -> bool:
        await self.get_or_raise(mark_id)
        return await self.mark_repo.delete(mark_id)
