"""Minimal deterministic truncation helpers."""

from __future__ import annotations

from newbee_notebook.core.context.token_counter import TokenCounter


class Compressor:
    def __init__(self, *, token_counter: TokenCounter):
        self._token_counter = token_counter

    def truncate(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0:
            return ""
        normalized = str(text or "").strip()
        if not normalized:
            return ""
        encoded = self._token_counter.encode(normalized)
        if len(encoded) <= max_tokens:
            return normalized
        return self._token_counter.decode(encoded[:max_tokens]).strip()

    def extract_first_paragraph(self, text: str) -> str:
        normalized = str(text or "").strip()
        if not normalized:
            return ""
        return normalized.split("\n\n", 1)[0].strip()

    def fit_messages(self, messages: list[dict], *, max_tokens: int) -> list[dict]:
        if max_tokens <= 0 or not messages:
            return []
        kept = list(messages)
        while kept and not self._token_counter.fits_budget(kept, max_tokens):
            if len(kept) == 1:
                overhead = self._token_counter.count_message_overhead(kept[0])
                content_budget = max(0, max_tokens - overhead)
                if content_budget <= 0:
                    return []
                kept = [
                    {
                        **kept[0],
                        "content": self.truncate(str(kept[0].get("content") or ""), content_budget),
                    }
                ]
                break
            kept = kept[1:]
        return kept
