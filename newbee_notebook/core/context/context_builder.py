"""Build OpenAI-compatible message lists from dual-track memory."""

from __future__ import annotations

from newbee_notebook.core.context.budget import ContextBudget
from newbee_notebook.core.context.compressor import Compressor
from newbee_notebook.core.context.session_memory import SessionMemory, StoredMessage
from newbee_notebook.core.context.token_counter import TokenCounter


class ContextBuilder:
    def __init__(
        self,
        *,
        memory: SessionMemory,
        token_counter: TokenCounter,
        compressor: Compressor,
    ):
        self._memory = memory
        self._token_counter = token_counter
        self._compressor = compressor

    @staticmethod
    def _to_message(item: StoredMessage) -> dict[str, str]:
        return {"role": item.role, "content": item.content}

    def _render_main_injection(self, items: list[StoredMessage]) -> dict[str, str] | None:
        if not items:
            return None
        lines = ["Recent main-track context:"]
        for item in items:
            lines.append(f"{item.role.upper()}: {item.content}")
        return {"role": "system", "content": "\n".join(lines)}

    def build(
        self,
        *,
        track: str,
        system_prompt: str,
        current_message: str,
        budget: ContextBudget,
        inject_main: bool = False,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

        if inject_main and str(track).strip().lower() == "side":
            main_history = self._memory.get_history("main")
            injected_messages = self._compressor.fit_messages(
                [self._to_message(item) for item in main_history],
                max_tokens=budget.main_injection,
            )
            injected = self._render_main_injection(
                [StoredMessage(role=item["role"], content=item["content"], mode="agent") for item in injected_messages]
            )
            if injected:
                messages.append(injected)

        history = self._memory.get_history(track)
        trimmed_history = self._compressor.fit_messages(
            [self._to_message(item) for item in history],
            max_tokens=budget.history,
        )
        messages.extend(trimmed_history)
        messages.append({"role": "user", "content": current_message})
        return messages
