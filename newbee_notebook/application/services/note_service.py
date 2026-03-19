"""Application service for notes."""

import re
from typing import Optional

from newbee_notebook.domain.entities.note import Note
from newbee_notebook.domain.repositories.note_repository import NoteRepository


MARK_REF_PATTERN = re.compile(r"\[\[mark:([A-Za-z0-9-]+)\]\]")


class NoteNotFoundError(Exception):
    """Raised when a note does not exist."""


class NoteService:
    """CRUD-style service for notebook notes."""

    def __init__(self, note_repo: NoteRepository):
        self.note_repo = note_repo

    async def create(
        self,
        notebook_id: str,
        title: str = "",
        content: str = "",
    ) -> Note:
        note = Note(
            notebook_id=notebook_id,
            title=title,
            content=content,
        )
        created = await self.note_repo.create(note)
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

    async def list_by_notebook(self, notebook_id: str) -> list[Note]:
        return await self.note_repo.list_by_notebook(notebook_id)

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

    def _extract_mark_ids(self, content: str) -> list[str]:
        return list(dict.fromkeys(MARK_REF_PATTERN.findall(content)))
