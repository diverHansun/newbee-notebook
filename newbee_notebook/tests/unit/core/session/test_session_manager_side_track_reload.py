from unittest.mock import AsyncMock

import pytest

from newbee_notebook.core.session.session_manager import SessionManager
from newbee_notebook.domain.entities.message import Message
from newbee_notebook.domain.entities.session import Session
from newbee_notebook.domain.value_objects.mode_type import MessageRole, ModeType


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_reload_memory_keeps_latest_side_track_messages_in_chronological_order():
    session_repo = AsyncMock()
    session_repo.get.return_value = Session(session_id="s1", notebook_id="nb1")

    message_repo = AsyncMock()
    message_repo.list_after_boundary.return_value = []
    message_repo.list_by_session.return_value = [
        Message(
            session_id="s1",
            mode=ModeType.CONCLUDE,
            role=MessageRole.ASSISTANT,
            content="new answer",
        ),
        Message(
            session_id="s1",
            mode=ModeType.CONCLUDE,
            role=MessageRole.USER,
            content="new question",
        ),
        Message(
            session_id="s1",
            mode=ModeType.EXPLAIN,
            role=MessageRole.ASSISTANT,
            content="old answer",
        ),
        Message(
            session_id="s1",
            mode=ModeType.EXPLAIN,
            role=MessageRole.USER,
            content="old question",
        ),
    ]

    manager = SessionManager(
        session_repo=session_repo,
        message_repo=message_repo,
        llm_client=object(),
        tool_registry=AsyncMock(),
        lock_manager=None,
        system_prompt_provider=lambda mode: f"prompt:{mode.value}",
    )

    await manager.start_session(session_id="s1")

    history = manager._memory.get_history("side")

    message_repo.list_by_session.assert_awaited_once_with(
        "s1",
        limit=12,
        modes=list(SessionManager.SIDE_TRACK_MODES),
        descending=True,
    )
    assert [item.content for item in history] == [
        "old question",
        "old answer",
        "new question",
        "new answer",
    ]