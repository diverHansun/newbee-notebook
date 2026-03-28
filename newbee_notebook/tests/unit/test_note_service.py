from datetime import datetime
from unittest.mock import AsyncMock
import uuid

import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from newbee_notebook.application.services.note_service import NoteNotFoundError, NoteService
from newbee_notebook.domain.entities.note import Note
from newbee_notebook.infrastructure.persistence.models import (
    NoteDocumentTagModel,
    NoteMarkRefModel,
    NoteModel,
    NotebookModel,
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


@pytest.mark.anyio
async def test_list_all_returns_all_notes():
    repo = AsyncMock()
    repo.list_all.return_value = [
        Note(note_id="n1", notebook_id="nb1", title="A", content=""),
        Note(note_id="n2", notebook_id="nb2", title="B", content=""),
    ]
    service = NoteService(repo)

    result = await service.list_all()

    assert len(result) == 2
    repo.list_all.assert_awaited_once()


@pytest.mark.anyio
async def test_list_all_filters_by_document_id():
    repo = AsyncMock()
    repo.list_all.return_value = [
        Note(note_id="n1", notebook_id="nb1", title="A", content="", document_ids=["d1"]),
        Note(note_id="n2", notebook_id="nb1", title="B", content="", document_ids=["d2"]),
        Note(note_id="n3", notebook_id="nb1", title="C", content="", document_ids=["d1", "d2"]),
    ]
    service = NoteService(repo)

    result = await service.list_all(document_id="d1")

    assert len(result) == 2
    assert {n.note_id for n in result} == {"n1", "n3"}


@pytest.mark.anyio
async def test_list_all_sorts_by_created_at_asc():
    repo = AsyncMock()
    repo.list_all.return_value = [
        Note(note_id="n1", notebook_id="nb1", title="A", content="", created_at=datetime(2025, 1, 3)),
        Note(note_id="n2", notebook_id="nb1", title="B", content="", created_at=datetime(2025, 1, 1)),
        Note(note_id="n3", notebook_id="nb1", title="C", content="", created_at=datetime(2025, 1, 2)),
    ]
    service = NoteService(repo)

    result = await service.list_all(sort_by="created_at", order="asc")

    assert [n.note_id for n in result] == ["n2", "n3", "n1"]


@pytest.mark.anyio
async def test_list_all_sorts_by_updated_at_desc():
    repo = AsyncMock()
    repo.list_all.return_value = [
        Note(note_id="n1", notebook_id="nb1", title="A", content="", updated_at=datetime(2025, 1, 1)),
        Note(note_id="n2", notebook_id="nb1", title="B", content="", updated_at=datetime(2025, 1, 3)),
        Note(note_id="n3", notebook_id="nb1", title="C", content="", updated_at=datetime(2025, 1, 2)),
    ]
    service = NoteService(repo)

    result = await service.list_all(sort_by="updated_at", order="desc")

    assert [n.note_id for n in result] == ["n2", "n3", "n1"]


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
        await conn.run_sync(NotebookModel.__table__.create)
        await conn.run_sync(NoteModel.__table__.create)
        await conn.execute(
            insert(NotebookModel).values(
                id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                title="Notebook",
            )
        )

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
