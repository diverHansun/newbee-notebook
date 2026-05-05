"""Slash-command registry for request-scoped skill activation."""

from __future__ import annotations

from newbee_notebook.core.skills.errors import SkillNameConflictError
from newbee_notebook.core.skills.contracts import SkillProvider


class SkillRegistry:
    def __init__(self) -> None:
        self._providers: list[SkillProvider] = []

    def register(self, provider: SkillProvider) -> None:
        provider_name = str(provider.skill_name)
        provider_commands = set(provider.slash_commands)
        for existing in self._providers:
            if str(existing.skill_name) == provider_name:
                raise SkillNameConflictError(f"skill already registered: {provider_name}")
            duplicate_commands = provider_commands.intersection(existing.slash_commands)
            if duplicate_commands:
                duplicate = sorted(duplicate_commands)[0]
                raise SkillNameConflictError(f"slash command already registered: {duplicate}")
        self._providers.append(provider)

    def unregister(self, skill_name: str) -> None:
        normalized = str(skill_name or "").strip()
        self._providers = [
            provider
            for provider in self._providers
            if str(provider.skill_name) != normalized
        ]

    def list_providers(self) -> list[SkillProvider]:
        return list(self._providers)

    def match_command(self, message: str) -> tuple[SkillProvider, str, str] | None:
        stripped = str(message or "").strip()
        if not stripped.startswith("/"):
            return None

        for provider in self._providers:
            if not bool(getattr(provider, "enabled", True)):
                continue
            for command in provider.slash_commands:
                if stripped == command:
                    return provider, command, ""
                if stripped.startswith(command + " "):
                    return provider, command, stripped[len(command) :].strip()
        return None
