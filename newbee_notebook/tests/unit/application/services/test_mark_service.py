from datetime import datetime
import uuid
from unittest.mock import AsyncMock

import pytest

from newbee_notebook.application.services.mark_service import MarkNotFoundError, MarkService
from newbee_notebook.domain.entities.mark import Mark
from newbee_notebook.infrastructure.persistence.models import MarkModel
from newbee_notebook.infrastructure.persistence.repositories.mark_repo_impl import MarkRepositoryImpl


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_create_mark_returns_saved_entity():
    repo = AsyncMock()
    repo.create.return_value = Mark(
        mark_id="m1",
        document_id="d1",
        anchor_text="abc",
        char_offset=12,
        context_text="ctx",
    )
    service = MarkService(repo)

    result = await service.create("d1", "abc", 12, context_text="ctx")

    assert result.mark_id == "m1"
    created = repo.create.await_args.args[0]
    assert created.document_id == "d1"
    assert created.anchor_text == "abc"
    assert created.char_offset == 12
    assert created.context_text == "ctx"


@pytest.mark.anyio
async def test_delete_mark_raises_for_missing_mark():
    repo = AsyncMock()
    repo.get.return_value = None
    service = MarkService(repo)

    with pytest.raises(MarkNotFoundError):
        await service.delete("missing")


def test_mark_repository_impl_maps_model_to_entity():
    mark_id = uuid.uuid4()
    document_id = uuid.uuid4()
    created_at = datetime(2026, 3, 19, 10, 0, 0)
    updated_at = datetime(2026, 3, 19, 10, 5, 0)
    model = MarkModel(
        id=mark_id,
        document_id=document_id,
        anchor_text="anchor",
        char_offset=42,
        context_text="context",
        created_at=created_at,
        updated_at=updated_at,
    )

    entity = MarkRepositoryImpl(AsyncMock())._to_entity(model)

    assert entity.mark_id == str(mark_id)
    assert entity.document_id == str(document_id)
    assert entity.anchor_text == "anchor"
    assert entity.char_offset == 42
    assert entity.context_text == "context"
    assert entity.created_at == created_at
    assert entity.updated_at == updated_at
