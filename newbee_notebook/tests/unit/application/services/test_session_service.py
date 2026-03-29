from unittest.mock import AsyncMock

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
