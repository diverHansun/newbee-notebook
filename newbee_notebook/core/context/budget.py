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
