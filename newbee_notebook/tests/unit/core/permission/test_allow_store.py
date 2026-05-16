from __future__ import annotations

import pytest

from newbee_notebook.core.permission import AllowStore


class _FakeSettingsService:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.deleted: list[str] = []

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def get_many(self, prefix: str) -> dict[str, str]:
        return {
            key: value
            for key, value in self.values.items()
            if key.startswith(prefix)
        }

    async def set(self, key: str, value: str) -> None:
        self.values[key] = value

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.values.pop(key, None)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_allow_store_uses_content_hash_bound_permission_key():
    settings = _FakeSettingsService()
    store = AllowStore(settings)

    await store.write("skill:demo@hash123:write_file:abc12345")

    expected_key = (
        "permissions.user_local.skill:demo@hash123.allow."
        "skill:demo@hash123:write_file:abc12345"
    )
    assert settings.values[expected_key] == "true"
    assert await store.contains("skill:demo@hash123:write_file:abc12345")
    assert not await store.contains("skill:demo@newhash:write_file:abc12345")


@pytest.mark.anyio
async def test_allow_store_treats_global_scope_as_separate_permission_namespace():
    settings = _FakeSettingsService()
    store = AllowStore(settings)

    await store.write("global:image_generate:abc12345")

    assert settings.values == {
        "permissions.user_local.global.allow.global:image_generate:abc12345": "true"
    }
    assert await store.contains("global:image_generate:abc12345")


@pytest.mark.anyio
async def test_allow_store_delete_by_skill_only_removes_matching_skill_records():
    settings = _FakeSettingsService()
    settings.values.update(
        {
            "permissions.user_local.skill:demo@hash1.allow.skill:demo@hash1:write_file:abc12345": "true",
            "permissions.user_local.skill:demo-extra@hash1.allow.skill:demo-extra@hash1:write_file:abc12345": "true",
            "permissions.user_local.skill:other@hash1.allow.skill:other@hash1:write_file:def67890": "true",
            "permissions.user_local.global.allow.global:write_file:feedbeef": "true",
        }
    )
    store = AllowStore(settings)

    removed = await store.delete_by_skill("demo")

    assert removed == 1
    assert settings.deleted == [
        "permissions.user_local.skill:demo@hash1.allow.skill:demo@hash1:write_file:abc12345"
    ]
    assert "permissions.user_local.skill:demo-extra@hash1.allow.skill:demo-extra@hash1:write_file:abc12345" in settings.values
