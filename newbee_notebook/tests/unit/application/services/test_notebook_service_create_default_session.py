from unittest.mock import AsyncMock

import pytest

from newbee_notebook.application.services.notebook_service import NotebookService
from newbee_notebook.domain.entities.notebook import Notebook
from newbee_notebook.domain.entities.session import Session


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_create_creates_default_session_and_returns_refreshed_notebook():
    notebook_repo = AsyncMock()
    created_notebook = Notebook(
        notebook_id="nb-1",
        title="Notebook",
        description="desc",
        session_count=0,
    )
    refreshed_notebook = Notebook(
        notebook_id="nb-1",
        title="Notebook",
        description="desc",
        session_count=1,
    )
    notebook_repo.create.return_value = created_notebook
    notebook_repo.get.return_value = refreshed_notebook

    session_repo = AsyncMock()
    document_repo = AsyncMock()
    ref_repo = AsyncMock()

    service = NotebookService(
        notebook_repo=notebook_repo,
        document_repo=document_repo,
        session_repo=session_repo,
        ref_repo=ref_repo,
        storage=AsyncMock(),
    )

    result = await service.create("Notebook", "desc")

    created_session = session_repo.create.await_args.args[0]
    assert isinstance(created_session, Session)
    assert created_session.notebook_id == "nb-1"
    assert created_session.title is None
    assert created_session.include_ec_context is False
    notebook_repo.increment_session_count.assert_awaited_once_with("nb-1")
    notebook_repo.get.assert_awaited_once_with("nb-1")
    assert result == refreshed_notebook


@pytest.mark.anyio
async def test_create_does_not_increment_count_when_default_session_creation_fails():
    notebook_repo = AsyncMock()
    notebook_repo.create.return_value = Notebook(
        notebook_id="nb-1",
        title="Notebook",
        session_count=0,
    )

    session_repo = AsyncMock()
    session_repo.create.side_effect = RuntimeError("session create failed")

    service = NotebookService(
        notebook_repo=notebook_repo,
        document_repo=AsyncMock(),
        session_repo=session_repo,
        ref_repo=AsyncMock(),
        storage=AsyncMock(),
    )

    with pytest.raises(RuntimeError, match="session create failed"):
        await service.create("Notebook")

    notebook_repo.increment_session_count.assert_not_called()
    notebook_repo.get.assert_not_called()