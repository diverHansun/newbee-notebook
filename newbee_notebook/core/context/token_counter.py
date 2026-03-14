"""Deterministic token counting helpers for context construction."""

from __future__ import annotations


class TokenCounter:
    def count(self, text: str) -> int:
        normalized = str(text or "").strip()
        if not normalized:
            return 0
        return len([part for part in normalized.split(" ") if part])

    def count_messages(self, messages: list[dict]) -> int:
        total = 0
        for message in messages:
            content = message.get("content")
            if isinstance(content, list):
                content = " ".join(
                    str(part.get("text", ""))
                    for part in content
                    if isinstance(part, dict)
                )
            total += self.count(str(content or ""))
        return total

    def fits_budget(self, messages: list[dict], budget: int) -> bool:
        return self.count_messages(messages) <= max(0, budget)
