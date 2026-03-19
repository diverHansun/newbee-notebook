"""SQLAlchemy implementation of the note repository."""

import uuid
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from newbee_notebook.domain.entities.note import Note
from newbee_notebook.domain.repositories.note_repository import NoteRepository
from newbee_notebook.infrastructure.persistence.models import (
    NoteDocumentTagModel,
    NoteMarkRefModel,
    NoteModel,
)


class NoteRepositoryImpl(NoteRepository):
    """SQLAlchemy-backed note repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    def _query(self):
        return select(NoteModel).options(
            selectinload(NoteModel.document_tags),
            selectinload(NoteModel.mark_refs),
        )

    def _to_entity(self, model: NoteModel) -> Note:
        return Note(
            note_id=str(model.id),
            notebook_id=str(model.notebook_id),
            title=model.title,
            content=model.content,
            document_ids=[str(item.document_id) for item in model.document_tags],
            mark_ids=[str(item.mark_id) for item in model.mark_refs],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get(self, note_id: str) -> Optional[Note]:
        result = await self._session.execute(
            self._query().where(NoteModel.id == uuid.UUID(note_id))
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_notebook(self, notebook_id: str) -> list[Note]:
        result = await self._session.execute(
            self._query()
            .where(NoteModel.notebook_id == uuid.UUID(notebook_id))
            .order_by(NoteModel.updated_at.desc(), NoteModel.created_at.desc())
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def create(self, note: Note) -> Note:
        model = NoteModel(
            id=uuid.UUID(note.note_id),
            notebook_id=uuid.UUID(note.notebook_id),
            title=note.title,
            content=note.content,
            created_at=note.created_at,
            updated_at=note.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def update(self, note: Note) -> Note:
        result = await self._session.execute(
            self._query().where(NoteModel.id == uuid.UUID(note.note_id))
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"Note not found during update: {note.note_id}")

        model.title = note.title
        model.content = note.content
        model.updated_at = note.updated_at
        await self._session.flush()
        return self._to_entity(model)

    async def delete(self, note_id: str) -> bool:
        result = await self._session.execute(
            delete(NoteModel).where(NoteModel.id == uuid.UUID(note_id))
        )
        await self._session.flush()
        return result.rowcount > 0

    async def sync_mark_refs(self, note_id: str, mark_ids: list[str]) -> None:
        note_uuid = uuid.UUID(note_id)
        result = await self._session.execute(
            select(NoteMarkRefModel).where(NoteMarkRefModel.note_id == note_uuid)
        )
        existing_rows = result.scalars().all()
        existing_map = {str(row.mark_id): row for row in existing_rows}
        target_ids = set(mark_ids)

        for current_mark_id, row in existing_map.items():
            if current_mark_id not in target_ids:
                await self._session.delete(row)

        for mark_id in mark_ids:
            if mark_id not in existing_map:
                self._session.add(
                    NoteMarkRefModel(
                        note_id=note_uuid,
                        mark_id=uuid.UUID(mark_id),
                    )
                )

        await self._session.flush()
