"""Slash-command registry for request-scoped skill activation."""

from __future__ import annotations

from newbee_notebook.core.skills.contracts import SkillProvider


class SkillRegistry:
    def __init__(self) -> None:
        self._providers: list[SkillProvider] = []

    def register(self, provider: SkillProvider) -> None:
        self._providers.append(provider)

    def match_command(self, message: str) -> tuple[SkillProvider, str, str] | None:
        stripped = str(message or "").strip()
        if not stripped.startswith("/"):
            return None

        for provider in self._providers:
            for command in provider.slash_commands:
                if stripped == command:
                    return provider, command, ""
                if stripped.startswith(command + " "):
                    return provider, command, stripped[len(command) :].strip()
        return None
