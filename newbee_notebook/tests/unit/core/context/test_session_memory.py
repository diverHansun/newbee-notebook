from __future__ import annotations

from newbee_notebook.core.context.session_memory import SessionMemory, StoredMessage


def _msg(role: str, content: str, mode: str = "agent") -> StoredMessage:
    return StoredMessage(role=role, content=content, mode=mode)


def test_session_memory_keeps_main_and_side_tracks_isolated():
    memory = SessionMemory(side_max_messages=4)

    memory.append("main", [_msg("user", "main user"), _msg("assistant", "main answer")])
    memory.append("side", [_msg("user", "side user", mode="explain")])

    assert [item.content for item in memory.get_history("main")] == ["main user", "main answer"]
    assert [item.content for item in memory.get_history("side")] == ["side user"]


def test_session_memory_load_from_messages_restores_both_tracks():
    memory = SessionMemory(side_max_messages=4)

    memory.load_from_messages(
        main_messages=[_msg("user", "ask 1", mode="ask")],
        side_messages=[_msg("assistant", "explain 1", mode="explain")],
    )

    assert [item.mode for item in memory.get_history("main")] == ["ask"]
    assert [item.mode for item in memory.get_history("side")] == ["explain"]


def test_session_memory_trims_side_track_to_capacity():
    memory = SessionMemory(side_max_messages=2)

    memory.append(
        "side",
        [
            _msg("user", "one", mode="explain"),
            _msg("assistant", "two", mode="explain"),
            _msg("user", "three", mode="conclude"),
        ],
    )

    assert [item.content for item in memory.get_history("side")] == ["two", "three"]


def test_session_memory_reset_clears_both_tracks():
    memory = SessionMemory()
    memory.append("main", [_msg("user", "main")])
    memory.append("side", [_msg("assistant", "side", mode="explain")])

    memory.reset()
    assert memory.get_history("main") == []
    assert memory.get_history("side") == []
