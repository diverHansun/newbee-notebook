"""Minimal deterministic truncation helpers."""

from __future__ import annotations

from newbee_notebook.core.context.token_counter import TokenCounter


class Compressor:
    def __init__(self, *, token_counter: TokenCounter):
        self._token_counter = token_counter

    def truncate(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0:
            return ""
        words = [part for part in str(text or "").split(" ") if part]
        return " ".join(words[:max_tokens])

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
                kept = [
                    {
                        **kept[0],
                        "content": self.truncate(str(kept[0].get("content") or ""), max_tokens),
                    }
                ]
                break
            kept = kept[1:]
        return kept
