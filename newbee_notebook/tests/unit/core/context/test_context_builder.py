from __future__ import annotations

from newbee_notebook.core.context.budget import ContextBudget
from newbee_notebook.core.context.compressor import Compressor
from newbee_notebook.core.context.context_builder import ContextBuilder
from newbee_notebook.core.context.session_memory import SessionMemory, StoredMessage
from newbee_notebook.core.context.token_counter import TokenCounter


class _WordTokenCounter(TokenCounter):
    def count(self, text: str) -> int:
        return len([part for part in text.split(" ") if part])


def _msg(role: str, content: str, mode: str = "agent") -> StoredMessage:
    return StoredMessage(role=role, content=content, mode=mode)


def test_context_builder_outputs_openai_compatible_messages_for_main_track():
    memory = SessionMemory()
    memory.append("main", [_msg("user", "hello world"), _msg("assistant", "hi there")])
    counter = _WordTokenCounter()
    builder = ContextBuilder(
        memory=memory,
        token_counter=counter,
        compressor=Compressor(token_counter=counter),
    )
    budget = ContextBudget(total=100, system_prompt=10, history=20, current_message=10, tool_results=0, output_reserved=10, main_injection=10)

    messages = builder.build(
        track="main",
        system_prompt="system prompt",
        current_message="follow up",
        budget=budget,
    )

    assert messages == [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "hello world"},
        {"role": "assistant", "content": "hi there"},
        {"role": "user", "content": "follow up"},
    ]


def test_context_builder_injects_recent_main_history_for_side_track_reads():
    memory = SessionMemory()
    memory.append(
        "main",
        [
            _msg("user", "main older context"),
            _msg("assistant", "main newer context"),
        ],
    )
    memory.append("side", [_msg("assistant", "side history", mode="explain")])
    counter = _WordTokenCounter()
    builder = ContextBuilder(
        memory=memory,
        token_counter=counter,
        compressor=Compressor(token_counter=counter),
    )
    budget = ContextBudget(total=100, system_prompt=10, history=20, current_message=10, tool_results=0, output_reserved=10, main_injection=4)

    messages = builder.build(
        track="side",
        system_prompt="explain system",
        current_message="explain this",
        budget=budget,
        inject_main=True,
    )

    assert messages[0] == {"role": "system", "content": "explain system"}
    assert messages[1]["role"] == "system"
    assert "Recent main-track context" in messages[1]["content"]
    assert "main newer context" in messages[1]["content"]
    assert "main older context" not in messages[1]["content"]
    assert messages[2] == {"role": "assistant", "content": "side history"}
    assert messages[3] == {"role": "user", "content": "explain this"}


def test_context_builder_truncates_history_deterministically_from_oldest_to_newest():
    memory = SessionMemory()
    memory.append(
        "main",
        [
            _msg("user", "one two three four"),
            _msg("assistant", "five six seven"),
            _msg("user", "eight nine"),
        ],
    )
    counter = _WordTokenCounter()
    builder = ContextBuilder(
        memory=memory,
        token_counter=counter,
        compressor=Compressor(token_counter=counter),
    )
    budget = ContextBudget(total=100, system_prompt=10, history=5, current_message=10, tool_results=0, output_reserved=10, main_injection=4)

    messages = builder.build(
        track="main",
        system_prompt="system",
        current_message="ten",
        budget=budget,
    )

    assert messages == [
        {"role": "system", "content": "system"},
        {"role": "assistant", "content": "five six seven"},
        {"role": "user", "content": "eight nine"},
        {"role": "user", "content": "ten"},
    ]
