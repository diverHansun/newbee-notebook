"""Deterministic token counting helpers for context construction."""

from __future__ import annotations

import tiktoken


class TokenCounter:
    def __init__(
        self,
        *,
        encoding_name: str = "cl100k_base",
        per_message_overhead: int = 4,
        reply_priming_tokens: int = 2,
    ):
        self._encoding = tiktoken.get_encoding(encoding_name)
        self._per_message_overhead = per_message_overhead
        self._reply_priming_tokens = reply_priming_tokens

    def count(self, text: str) -> int:
        normalized = str(text or "").strip()
        if not normalized:
            return 0
        return len(self._encoding.encode(normalized))

    def encode(self, text: str) -> list[int]:
        normalized = str(text or "").strip()
        if not normalized:
            return []
        return list(self._encoding.encode(normalized))

    def decode(self, tokens: list[int]) -> str:
        if not tokens:
            return ""
        return self._encoding.decode(tokens)

    @staticmethod
    def _message_content(message: dict) -> str:
        content = message.get("content")
        if isinstance(content, list):
            return " ".join(
                str(part.get("text", ""))
                for part in content
                if isinstance(part, dict)
            ).strip()
        return str(content or "")

    def count_message_overhead(self, message: dict) -> int:
        role = str(message.get("role") or "")
        return self._per_message_overhead + self.count(role)

    def count_messages(self, messages: list[dict]) -> int:
        if not messages:
            return 0

        total = self._reply_priming_tokens
        for message in messages:
            total += self.count_message_overhead(message)
            total += self.count(self._message_content(message))
        return total

    def fits_budget(self, messages: list[dict], budget: int) -> bool:
        return self.count_messages(messages) <= max(0, budget)
