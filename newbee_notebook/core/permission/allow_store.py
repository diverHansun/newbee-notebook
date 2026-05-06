"""Persistent permission allow store backed by app_settings."""

from __future__ import annotations

from typing import Protocol


class SettingsStoreProtocol(Protocol):
    async def get(self, key: str) -> str | None: ...

    async def get_many(self, prefix: str) -> dict[str, str]: ...

    async def set(self, key: str, value: str) -> None: ...

    async def delete(self, key: str) -> None: ...


def _scope_from_signature(capability_signature: str) -> str:
    parts = str(capability_signature or "").rsplit(":", 2)
    if len(parts) < 3:
        return "global"
    return parts[0] or "global"


class AllowStore:
    def __init__(self, settings_service: SettingsStoreProtocol, *, user_id: str = "local") -> None:
        self._settings_service = settings_service
        self._user_id = str(user_id or "local")

    def key_for(self, capability_signature: str) -> str:
        scope = _scope_from_signature(capability_signature)
        return f"permissions.user_{self._user_id}.{scope}.allow.{capability_signature}"

    async def contains(self, capability_signature: str) -> bool:
        if not str(capability_signature or "").strip():
            return False
        return (await self._settings_service.get(self.key_for(capability_signature))) is not None

    async def write(self, capability_signature: str) -> None:
        if not str(capability_signature or "").strip():
            raise ValueError("capability_signature is required")
        await self._settings_service.set(self.key_for(capability_signature), "true")

    async def delete_by_skill(self, skill_name: str) -> int:
        normalized_name = str(skill_name or "").strip()
        if not normalized_name:
            return 0
        marker = f".skill:{normalized_name}@"
        values = await self._settings_service.get_many("permissions.")
        keys = [
            key
            for key in values
            if marker in key and ".allow." in key
        ]
        for key in keys:
            await self._settings_service.delete(key)
        return len(keys)
