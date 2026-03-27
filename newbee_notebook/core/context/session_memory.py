"""Dual-track session memory for the new runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StoredMessage:
    role: str
    content: str
    mode: str
    message_type: str = "normal"
    metadata: dict[str, Any] = field(default_factory=dict)


class SessionMemory:
    def __init__(self, *, side_max_messages: int = 12):
        self._main_history: list[StoredMessage] = []
        self._side_history: list[StoredMessage] = []
        self._side_max_messages = side_max_messages
        self._summary: str | None = None
        self._summary_stale = True

    def get_history(self, track: str) -> list[StoredMessage]:
        normalized = str(track).strip().lower()
        if normalized == "main":
            return list(self._main_history)
        if normalized == "side":
            return list(self._side_history)
        raise ValueError(f"unknown track: {track}")

    def append(self, track: str, messages: list[StoredMessage]) -> None:
        normalized = str(track).strip().lower()
        if normalized == "main":
            self._main_history.extend(messages)
        elif normalized == "side":
            self._side_history.extend(messages)
            if self._side_max_messages > 0:
                self._side_history = self._side_history[-self._side_max_messages :]
        else:
            raise ValueError(f"unknown track: {track}")
        self._summary_stale = True

    def load_from_messages(
        self,
        main_messages: list[StoredMessage],
        side_messages: list[StoredMessage],
    ) -> None:
        self._main_history = list(main_messages)
        self._side_history = list(side_messages)
        if self._side_max_messages > 0:
            self._side_history = self._side_history[-self._side_max_messages :]
        self._summary_stale = True

    def get_summary(self) -> str | None:
        if self._summary_stale:
            return None
        return self._summary

    def set_summary(self, summary: str) -> None:
        self._summary = summary
        self._summary_stale = False

    def mark_summary_stale(self) -> None:
        self._summary_stale = True

    def reset(self) -> None:
        self._main_history = []
        self._side_history = []
        self._summary = None
        self._summary_stale = True
