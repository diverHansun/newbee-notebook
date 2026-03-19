from unittest.mock import AsyncMock
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from newbee_notebook.application.services.note_service import NoteNotFoundError, NoteService
from newbee_notebook.domain.entities.note import Note
from newbee_notebook.infrastructure.persistence.models import (
    Base,
    NoteDocumentTagModel,
    NoteMarkRefModel,
    NoteModel,
)
from newbee_notebook.infrastructure.persistence.repositories.note_repo_impl import NoteRepositoryImpl


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_update_note_syncs_mark_refs():
    repo = AsyncMock()
    repo.get.return_value = Note(
        note_id="n1",
        notebook_id="nb1",
        title="old",
        content="before",
    )
    repo.update.return_value = Note(
        note_id="n1",
        notebook_id="nb1",
        title="T",
        content="See [[mark:m1]] and [[mark:m1]] plus [[mark:m2]]",
        mark_ids=["m1", "m2"],
    )
    service = NoteService(repo)

    result = await service.update(
        "n1",
        title="T",
        content="See [[mark:m1]] and [[mark:m1]] plus [[mark:m2]]",
    )

    updated = repo.update.await_args.args[0]
    assert updated.note_id == "n1"
    assert updated.title == "T"
    assert updated.content == "See [[mark:m1]] and [[mark:m1]] plus [[mark:m2]]"
    repo.sync_mark_refs.assert_awaited_once_with("n1", ["m1", "m2"])
    assert result.mark_ids == ["m1", "m2"]


@pytest.mark.anyio
async def test_list_notes_scopes_to_notebook():
    repo = AsyncMock()
    repo.list_by_notebook.return_value = []
    service = NoteService(repo)

    result = await service.list_by_notebook("nb1")

    assert result == []
    repo.list_by_notebook.assert_awaited_once_with("nb1")


@pytest.mark.anyio
async def test_delete_note_raises_for_missing_note():
    repo = AsyncMock()
    repo.get.return_value = None
    service = NoteService(repo)

    with pytest.raises(NoteNotFoundError):
        await service.delete("missing")


def test_note_repository_impl_maps_model_to_entity_with_related_ids():
    note_id = uuid.uuid4()
    notebook_id = uuid.uuid4()
    document_id = uuid.uuid4()
    mark_id = uuid.uuid4()
    model = NoteModel(
        id=note_id,
        notebook_id=notebook_id,
        title="Title",
        content="Body",
    )
    model.document_tags = [NoteDocumentTagModel(document_id=document_id)]
    model.mark_refs = [NoteMarkRefModel(mark_id=mark_id)]

    entity = NoteRepositoryImpl(AsyncMock())._to_entity(model)

    assert entity.note_id == str(note_id)
    assert entity.notebook_id == str(notebook_id)
    assert entity.title == "Title"
    assert entity.content == "Body"
    assert entity.document_ids == [str(document_id)]
    assert entity.mark_ids == [str(mark_id)]


@pytest.mark.anyio
async def test_note_repository_create_returns_note_without_lazy_loading():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as session:
            repo = NoteRepositoryImpl(session)
            created = await repo.create(
                Note(
                    notebook_id="00000000-0000-0000-0000-000000000001",
                    title="",
                    content="",
                )
            )
    finally:
        await engine.dispose()

    assert created.title == ""
    assert created.content == ""
    assert created.document_ids == []
    assert created.mark_ids == []
