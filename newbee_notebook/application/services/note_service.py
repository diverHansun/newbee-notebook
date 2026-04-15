"""Application service for notes."""

import re
from typing import Optional

from newbee_notebook.domain.entities.note import Note
from newbee_notebook.domain.repositories.note_repository import NoteRepository
from newbee_notebook.domain.repositories.reference_repository import (
    NotebookDocumentRefRepository,
)


MARK_REF_PATTERN = re.compile(r"\[\[mark:([A-Za-z0-9-]+)\]\]")


class NoteNotFoundError(Exception):
    """Raised when a note does not exist."""


class NoteService:
    """CRUD-style service for notebook notes."""

    def __init__(
        self,
        note_repo: NoteRepository,
        ref_repo: Optional[NotebookDocumentRefRepository] = None,
    ):
        self.note_repo = note_repo
        self.ref_repo = ref_repo

    async def create(
        self,
        notebook_id: str,
        title: str = "",
        content: str = "",
        document_ids: Optional[list[str]] = None,
    ) -> Note:
        note = Note(
            notebook_id=notebook_id,
            title=title,
            content=content,
        )
        created = await self.note_repo.create(note)
        for document_id in document_ids or []:
            await self._ensure_document_in_notebook(notebook_id, document_id)
            await self.note_repo.add_document_tag(created.note_id, document_id)
        created.document_ids = list(document_ids or [])
        mark_ids = self._extract_mark_ids(created.content)
        await self.note_repo.sync_mark_refs(created.note_id, mark_ids)
        created.mark_ids = mark_ids
        return created

    async def get(self, note_id: str) -> Optional[Note]:
        return await self.note_repo.get(note_id)

    async def get_or_raise(self, note_id: str) -> Note:
        note = await self.get(note_id)
        if not note:
            raise NoteNotFoundError(f"Note not found: {note_id}")
        return note

    async def list_all(
        self,
        document_id: Optional[str] = None,
        sort_by: str = "updated_at",
        order: str = "desc",
    ) -> list[Note]:
        """List all notes, optionally filtered by document and sorted."""
        notes = await self.note_repo.list_all()

        if document_id:
            notes = [n for n in notes if document_id in n.document_ids]

        reverse = order == "desc"
        if sort_by == "created_at":
            notes.sort(key=lambda n: n.created_at, reverse=reverse)
        else:
            notes.sort(key=lambda n: n.updated_at, reverse=reverse)

        return notes

    async def list_all_paginated(
        self,
        document_id: Optional[str] = None,
        sort_by: str = "updated_at",
        order: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Note], int]:
        notes = await self.note_repo.list_all_paginated(
            document_id=document_id,
            sort_by=sort_by,
            order=order,
            limit=limit,
            offset=offset,
        )
        total = await self.note_repo.count_all(document_id=document_id)
        return notes, total

    async def list_by_notebook(
        self,
        notebook_id: str,
        document_id: Optional[str] = None,
    ) -> list[Note]:
        if document_id is None:
            return await self.note_repo.list_by_notebook(notebook_id)
        return await self.note_repo.list_by_notebook(
            notebook_id,
            document_id=document_id,
        )

    async def list_by_notebook_paginated(
        self,
        notebook_id: str,
        document_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Note], int]:
        notes = await self.note_repo.list_by_notebook_paginated(
            notebook_id,
            document_id=document_id,
            limit=limit,
            offset=offset,
        )
        total = await self.note_repo.count_by_notebook(
            notebook_id,
            document_id=document_id,
        )
        return notes, total

    async def update(
        self,
        note_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
    ) -> Note:
        note = await self.get_or_raise(note_id)
        if title is not None:
            note.title = title
        if content is not None:
            note.content = content
        note.touch()

        updated = await self.note_repo.update(note)
        mark_ids = self._extract_mark_ids(updated.content)
        await self.note_repo.sync_mark_refs(note_id, mark_ids)
        updated.mark_ids = mark_ids
        return updated

    async def delete(self, note_id: str) -> bool:
        await self.get_or_raise(note_id)
        return await self.note_repo.delete(note_id)

    async def add_document_tag(self, note_id: str, document_id: str) -> None:
        note = await self.get_or_raise(note_id)
        await self._ensure_document_in_notebook(note.notebook_id, document_id)
        await self.note_repo.add_document_tag(note_id, document_id)

    async def remove_document_tag(self, note_id: str, document_id: str) -> bool:
        await self.get_or_raise(note_id)
        return await self.note_repo.remove_document_tag(note_id, document_id)

    def _extract_mark_ids(self, content: str) -> list[str]:
        return list(dict.fromkeys(MARK_REF_PATTERN.findall(content)))

    async def _ensure_document_in_notebook(self, notebook_id: str, document_id: str) -> None:
        if self.ref_repo is None:
            return
        existing = await self.ref_repo.get_by_notebook_and_document(notebook_id, document_id)
        if existing is None:
            raise ValueError(
                f"Document {document_id} is not associated with notebook {notebook_id}"
            )
