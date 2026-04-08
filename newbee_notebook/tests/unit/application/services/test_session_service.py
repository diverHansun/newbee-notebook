from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest

from newbee_notebook.application.services.session_service import (
    SessionLimitExceededError,
    SessionService,
)
from newbee_notebook.domain.entities.session import Session


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_create_allows_up_to_49_existing_sessions():
    session_repo = AsyncMock()
    notebook_repo = AsyncMock()
    message_repo = AsyncMock()

    notebook_repo.get.return_value = object()
    session_repo.count_by_notebook.return_value = 49
    session_repo.create.return_value = Session(
        session_id="session-50",
        notebook_id="nb-1",
        title="Session 50",
    )

    service = SessionService(session_repo, notebook_repo, message_repo)

    result = await service.create("nb-1", title="Session 50")

    assert result.session_id == "session-50"
    session_repo.create.assert_awaited_once()
    notebook_repo.increment_session_count.assert_awaited_once_with("nb-1")


@pytest.mark.anyio
async def test_create_raises_limit_error_when_notebook_already_has_50_sessions():
    session_repo = AsyncMock()
    notebook_repo = AsyncMock()
    message_repo = AsyncMock()

    notebook_repo.get.return_value = object()
    session_repo.count_by_notebook.return_value = 50

    service = SessionService(session_repo, notebook_repo, message_repo)

    with pytest.raises(SessionLimitExceededError) as exc_info:
        await service.create("nb-1")

    assert exc_info.value.current_count == 50
    assert exc_info.value.max_count == 50
    session_repo.create.assert_not_called()
    notebook_repo.increment_session_count.assert_not_called()


@pytest.mark.anyio
async def test_delete_session_removes_generated_image_objects_before_db_delete():
    session_repo = AsyncMock()
    notebook_repo = AsyncMock()
    message_repo = AsyncMock()
    generated_image_repo = AsyncMock()
    storage = AsyncMock()

    service = SessionService(
        session_repo=session_repo,
        notebook_repo=notebook_repo,
        message_repo=message_repo,
        generated_image_repo=generated_image_repo,
        storage=storage,
    )

    service.get_or_raise = AsyncMock(
        return_value=Session(
            session_id="session-1",
            notebook_id="nb-1",
            title="session",
        )
    )
    generated_image_repo.list_by_session.return_value = [
        SimpleNamespace(storage_key="generated-images/nb-1/session-1/img-1.png"),
        SimpleNamespace(storage_key="generated-images/nb-1/session-1/img-2.png"),
    ]
    session_repo.delete.return_value = True

    deleted = await service.delete("session-1")

    assert deleted is True
    generated_image_repo.list_by_session.assert_awaited_once_with("session-1")
    storage.delete_file.assert_any_await("generated-images/nb-1/session-1/img-1.png")
    storage.delete_file.assert_any_await("generated-images/nb-1/session-1/img-2.png")
    session_repo.delete.assert_awaited_once_with("session-1")
    notebook_repo.increment_session_count.assert_awaited_once_with("nb-1", -1)


@pytest.mark.anyio
async def test_delete_session_ignores_missing_generated_image_objects():
    session_repo = AsyncMock()
    notebook_repo = AsyncMock()
    message_repo = AsyncMock()
    generated_image_repo = AsyncMock()
    storage = AsyncMock()
    storage.delete_file = AsyncMock(side_effect=FileNotFoundError("missing"))

    service = SessionService(
        session_repo=session_repo,
        notebook_repo=notebook_repo,
        message_repo=message_repo,
        generated_image_repo=generated_image_repo,
        storage=storage,
    )

    service.get_or_raise = AsyncMock(
        return_value=Session(
            session_id="session-1",
            notebook_id="nb-1",
            title="session",
        )
    )
    generated_image_repo.list_by_session.return_value = [
        SimpleNamespace(storage_key="generated-images/nb-1/session-1/img-1.png"),
    ]
    session_repo.delete.return_value = True

    deleted = await service.delete("session-1")

    assert deleted is True
    storage.delete_file.assert_awaited_once_with("generated-images/nb-1/session-1/img-1.png")
    session_repo.delete.assert_awaited_once_with("session-1")
