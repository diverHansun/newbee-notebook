"""Budget structures for context construction."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextBudget:
    total: int
    system_prompt: int
    history: int
    current_message: int
    tool_results: int
    output_reserved: int
    main_injection: int
    summary: int = 0

    @property
    def compaction_threshold(self) -> int:
        return int(self.total * 0.95)
