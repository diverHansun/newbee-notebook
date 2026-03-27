from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from newbee_notebook.core.context.budget import ContextBudget
from newbee_notebook.core.context.compressor import Compressor
from newbee_notebook.core.context.compaction_service import CompactionService
from newbee_notebook.core.context.token_counter import TokenCounter
from newbee_notebook.domain.entities.message import Message
from newbee_notebook.domain.entities.session import Session
from newbee_notebook.domain.value_objects.mode_type import MessageRole, MessageType, ModeType


def _message(
    role: MessageRole,
    content: str,
    *,
    mode: ModeType = ModeType.AGENT,
    message_id: int | None = None,
    message_type: MessageType = MessageType.NORMAL,
) -> Message:
    return Message(
        message_id=message_id,
        session_id="session-1",
        mode=mode,
        role=role,
        message_type=message_type,
        content=content,
    )


def _budget(*, total: int, summary: int = 32) -> ContextBudget:
    return ContextBudget(
        total=total,
        system_prompt=128,
        history=128,
        current_message=64,
        tool_results=64,
        output_reserved=64,
        main_injection=64,
        summary=summary,
    )


def _response(text: str):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=text),
            )
        ]
    )


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_compaction_service_skips_when_history_is_below_threshold():
    session = Session(session_id="session-1", notebook_id="nb-1")
    message_repo = AsyncMock()
    message_repo.list_after_boundary.return_value = [
        _message(MessageRole.USER, "short question"),
        _message(MessageRole.ASSISTANT, "short answer"),
    ]
    session_repo = AsyncMock()
    llm_client = AsyncMock()

    service = CompactionService(
        message_repo=message_repo,
        session_repo=session_repo,
        llm_client=llm_client,
        token_counter=TokenCounter(),
        compressor=Compressor(token_counter=TokenCounter()),
        budget=_budget(total=10_000),
    )

    compacted = await service.compact_if_needed(
        session=session,
        track_modes=[ModeType.AGENT, ModeType.ASK],
    )

    assert compacted is False
    message_repo.list_after_boundary.assert_awaited_once_with(
        "session-1",
        None,
        track_modes=[ModeType.AGENT, ModeType.ASK],
    )
    llm_client.chat.assert_not_awaited()
    message_repo.create.assert_not_awaited()
    session_repo.update_compaction_boundary.assert_not_awaited()


@pytest.mark.anyio
async def test_compaction_service_creates_summary_and_updates_boundary():
    session = Session(session_id="session-1", notebook_id="nb-1")
    message_repo = AsyncMock()
    message_repo.list_after_boundary.return_value = [
        _message(MessageRole.USER, "Need a compact summary of the earlier planning discussion."),
        _message(MessageRole.ASSISTANT, "We decided to use a worktree and keep SUMMARY internal."),
    ]
    created_messages: list[Message] = []

    async def _create_summary(message: Message) -> Message:
        created_messages.append(message)
        return Message(
            message_id=88,
            session_id=message.session_id,
            mode=message.mode,
            role=message.role,
            message_type=message.message_type,
            content=message.content,
            created_at=message.created_at,
        )

    message_repo.create.side_effect = _create_summary
    session_repo = AsyncMock()
    llm_client = AsyncMock()
    llm_client.chat.return_value = _response("Summary keeps the worktree choice and internal SUMMARY handling.")

    service = CompactionService(
        message_repo=message_repo,
        session_repo=session_repo,
        llm_client=llm_client,
        token_counter=TokenCounter(),
        compressor=Compressor(token_counter=TokenCounter()),
        budget=_budget(total=20, summary=24),
    )

    compacted = await service.compact_if_needed(
        session=session,
        track_modes=[ModeType.AGENT, ModeType.ASK],
    )

    assert compacted is True
    assert created_messages[0].role is MessageRole.ASSISTANT
    assert created_messages[0].mode is ModeType.AGENT
    assert created_messages[0].message_type is MessageType.SUMMARY
    assert created_messages[0].content == "Summary keeps the worktree choice and internal SUMMARY handling."
    session_repo.update_compaction_boundary.assert_awaited_once_with("session-1", 88)
    assert session.compaction_boundary_id == 88

    llm_call = llm_client.chat.await_args.kwargs
    assert llm_call["disable_thinking"] is True
    assert llm_call["max_tokens"] == 24
    assert "tools" not in llm_call
    assert "tool_choice" not in llm_call

    prompt_messages = llm_call["messages"]
    assert prompt_messages[0]["role"] == "system"
    assert "compact assistant memory" in prompt_messages[0]["content"]
    assert "Need a compact summary" in prompt_messages[1]["content"]


@pytest.mark.anyio
async def test_compaction_service_rolls_previous_summary_into_new_summary_prompt():
    session = Session(
        session_id="session-1",
        notebook_id="nb-1",
        compaction_boundary_id=41,
    )
    message_repo = AsyncMock()
    message_repo.list_after_boundary.return_value = [
        _message(
            MessageRole.ASSISTANT,
            "Earlier summary about repository cleanup and testing.",
            message_id=41,
            message_type=MessageType.SUMMARY,
        ),
        _message(MessageRole.USER, "Now add worktree-based development to the plan."),
        _message(MessageRole.ASSISTANT, "We will use a temporary branch inside a dedicated worktree."),
    ]
    message_repo.create.side_effect = lambda message: Message(
        message_id=99,
        session_id=message.session_id,
        mode=message.mode,
        role=message.role,
        message_type=message.message_type,
        content=message.content,
        created_at=message.created_at,
    )
    session_repo = AsyncMock()
    llm_client = AsyncMock()
    llm_client.chat.return_value = _response("Merged summary")

    service = CompactionService(
        message_repo=message_repo,
        session_repo=session_repo,
        llm_client=llm_client,
        token_counter=TokenCounter(),
        compressor=Compressor(token_counter=TokenCounter()),
        budget=_budget(total=20, summary=32),
    )

    compacted = await service.compact_if_needed(
        session=session,
        track_modes=[ModeType.AGENT, ModeType.ASK],
    )

    assert compacted is True
    message_repo.list_after_boundary.assert_awaited_once_with(
        "session-1",
        41,
        track_modes=[ModeType.AGENT, ModeType.ASK],
    )
    prompt_body = llm_client.chat.await_args.kwargs["messages"][1]["content"]
    assert "[SUMMARY]" in prompt_body
    assert "Earlier summary about repository cleanup and testing." in prompt_body
    assert "Now add worktree-based development to the plan." in prompt_body


@pytest.mark.anyio
async def test_compaction_service_truncates_summary_to_summary_budget():
    session = Session(session_id="session-1", notebook_id="nb-1")
    message_repo = AsyncMock()
    message_repo.list_after_boundary.return_value = [
        _message(MessageRole.USER, "please summarize the long planning conversation"),
        _message(MessageRole.ASSISTANT, "there were many implementation details and constraints"),
    ]
    created_messages: list[Message] = []

    async def _capture_summary(message: Message) -> Message:
        created_messages.append(message)
        return Message(
            message_id=7,
            session_id=message.session_id,
            mode=message.mode,
            role=message.role,
            message_type=message.message_type,
            content=message.content,
            created_at=message.created_at,
        )

    message_repo.create.side_effect = _capture_summary
    session_repo = AsyncMock()
    llm_client = AsyncMock()
    llm_client.chat.return_value = _response(
        "summary token one two three four five six seven eight nine ten eleven twelve"
    )
    token_counter = TokenCounter()

    service = CompactionService(
        message_repo=message_repo,
        session_repo=session_repo,
        llm_client=llm_client,
        token_counter=token_counter,
        compressor=Compressor(token_counter=token_counter),
        budget=_budget(total=20, summary=6),
    )

    compacted = await service.compact_if_needed(
        session=session,
        track_modes=[ModeType.AGENT, ModeType.ASK],
    )

    assert compacted is True
    assert token_counter.count(created_messages[0].content) <= 6


@pytest.mark.anyio
async def test_compaction_service_logs_and_falls_back_when_llm_fails(caplog):
    session = Session(session_id="session-1", notebook_id="nb-1", compaction_boundary_id=12)
    message_repo = AsyncMock()
    message_repo.list_after_boundary.return_value = [
        _message(
            MessageRole.ASSISTANT,
            "Previous summary that still keeps enough context to trigger compaction.",
            message_id=12,
            message_type=MessageType.SUMMARY,
        ),
        _message(MessageRole.USER, "Add more details so we exceed the threshold again."),
    ]
    session_repo = AsyncMock()
    llm_client = AsyncMock()
    llm_client.chat.side_effect = RuntimeError("provider unavailable")

    service = CompactionService(
        message_repo=message_repo,
        session_repo=session_repo,
        llm_client=llm_client,
        token_counter=TokenCounter(),
        compressor=Compressor(token_counter=TokenCounter()),
        budget=_budget(total=20, summary=16),
    )

    with caplog.at_level(logging.WARNING):
        compacted = await service.compact_if_needed(
            session=session,
            track_modes=[ModeType.AGENT, ModeType.ASK],
        )

    assert compacted is False
    assert session.compaction_boundary_id == 12
    assert "session-1" in caplog.text
    assert "compaction failed" in caplog.text
    message_repo.create.assert_not_awaited()
    session_repo.update_compaction_boundary.assert_not_awaited()
