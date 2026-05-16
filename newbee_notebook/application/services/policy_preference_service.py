"""Notebook/session-scoped agent policy preferences."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

AgentPolicyValue = Literal["default", "yolo"]
PolicySourceValue = Literal["default", "session", "notebook"]


class SettingsStore(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str) -> None: ...
    async def delete(self, key: str) -> None: ...


@dataclass(frozen=True)
class EffectivePolicy:
    notebook_id: str
    session_id: str | None
    policy: AgentPolicyValue
    source: PolicySourceValue


class PolicyPreferenceService:
    def __init__(self, settings: SettingsStore) -> None:
        self._settings = settings

    @staticmethod
    def notebook_key(notebook_id: str) -> str:
        return f"policy.notebooks.{notebook_id}.agent_policy"

    @staticmethod
    def session_key(session_id: str) -> str:
        return f"policy.sessions.{session_id}.agent_policy"

    @staticmethod
    def _normalize(value: str | None) -> AgentPolicyValue:
        return "yolo" if str(value or "").strip().lower() == "yolo" else "default"

    async def get_effective(
        self,
        *,
        notebook_id: str,
        session_id: str | None = None,
    ) -> EffectivePolicy:
        if session_id:
            session_policy = self._normalize(
                await self._settings.get(self.session_key(session_id))
            )
            if session_policy == "yolo":
                return EffectivePolicy(notebook_id, session_id, "yolo", "session")

        notebook_policy = self._normalize(
            await self._settings.get(self.notebook_key(notebook_id))
        )
        if notebook_policy == "yolo":
            return EffectivePolicy(notebook_id, session_id, "yolo", "notebook")

        return EffectivePolicy(notebook_id, session_id, "default", "default")

    async def update_session(
        self,
        *,
        notebook_id: str,
        session_id: str,
        policy: AgentPolicyValue,
    ) -> EffectivePolicy:
        key = self.session_key(session_id)
        if policy == "yolo":
            await self._settings.set(key, "yolo")
        else:
            await self._settings.delete(key)
        return await self.get_effective(notebook_id=notebook_id, session_id=session_id)

    async def update_notebook(
        self,
        *,
        notebook_id: str,
        session_id: str | None,
        policy: AgentPolicyValue,
    ) -> EffectivePolicy:
        key = self.notebook_key(notebook_id)
        if policy == "yolo":
            await self._settings.set(key, "yolo")
        else:
            await self._settings.delete(key)
        return await self.get_effective(notebook_id=notebook_id, session_id=session_id)
