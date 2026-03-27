"""Prompt helpers for context compaction."""

from __future__ import annotations

from newbee_notebook.domain.entities.message import Message
from newbee_notebook.domain.value_objects.mode_type import MessageType


COMPACTION_SYSTEM_PROMPT = (
    "You are compressing prior assistant-visible conversation into compact assistant memory. "
    "Produce one concise summary that preserves durable facts, user preferences, decisions, "
    "open tasks, unresolved risks, and important file or workflow context. "
    "Do not invent details. Merge any previous summary into a fresh single summary. "
    "Keep the wording neutral and easy to reuse in later turns."
)


def _mode_value(message: Message) -> str:
    mode = message.mode
    return mode.value if hasattr(mode, "value") else str(mode)


def _type_label(message: Message) -> str:
    message_type = message.message_type
    value = message_type.value if hasattr(message_type, "value") else str(message_type)
    return "SUMMARY" if value == MessageType.SUMMARY.value else "NORMAL"


def render_compaction_transcript(messages: list[Message]) -> str:
    lines = [
        "Summarize the following conversation history into one compact assistant memory.",
        "Conversation history:",
    ]
    for item in messages:
        lines.append(
            f"[{_type_label(item)}][{_mode_value(item)}] {item.role.value.upper()}: {item.content}"
        )
    return "\n".join(lines)


def build_compaction_messages(messages: list[Message]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": COMPACTION_SYSTEM_PROMPT},
        {"role": "user", "content": render_compaction_transcript(messages)},
    ]
