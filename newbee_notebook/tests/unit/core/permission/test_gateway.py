from __future__ import annotations

import pytest

from newbee_notebook.core.engine.confirmation import ConfirmationGateway
from newbee_notebook.core.permission import (
    AllowStore,
    PermissionChoice,
    PermissionGateway,
    PermissionRequest,
    PermissionResponseKind,
    SessionAllowCache,
)


class _FakeSettingsService:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.raise_on_get = False
        self.raise_on_set = False

    async def get(self, key: str) -> str | None:
        if self.raise_on_get:
            raise RuntimeError("db read failed")
        return self.values.get(key)

    async def get_many(self, prefix: str) -> dict[str, str]:
        return {
            key: value
            for key, value in self.values.items()
            if key.startswith(prefix)
        }

    async def set(self, key: str, value: str) -> None:
        if self.raise_on_set:
            raise RuntimeError("db write failed")
        self.values[key] = value

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)


def _request(signature: str = "global:write_file:abc12345") -> PermissionRequest:
    return PermissionRequest(
        session_id="session-1",
        assistant_turn_id="turn-1",
        tool_call_id="call-1",
        capability_signature=signature,
        tool_name="write_file",
        args_summary={"path": "out.md"},
        risk_level="moderate",
    )


def test_session_allow_cache_can_allow_all_capabilities_in_session():
    cache = SessionAllowCache()

    cache.add_all("session-1")

    assert cache.contains("session-1", "global:bash:abc")
    assert cache.contains("session-1", "global:write_file:def")
    assert not cache.contains("session-2", "global:bash:abc")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_confirmation_gateway_supports_rich_response_and_legacy_bool():
    gateway = ConfirmationGateway()
    gateway.create("req-rich")
    assert gateway.resolve_response("req-rich", {"response": "always_session"})
    assert await gateway.wait_response("req-rich") == {"response": "always_session"}

    gateway.create("req-legacy")
    assert gateway.resolve("req-legacy", approved=True)
    assert await gateway.wait("req-legacy")


@pytest.mark.anyio
async def test_permission_gateway_allows_when_session_cache_matches_without_confirmation():
    settings = _FakeSettingsService()
    cache = SessionAllowCache()
    cache.add("session-1", "global:write_file:abc12345")
    gateway = PermissionGateway(
        allow_store=AllowStore(settings),
        session_cache=cache,
        confirmation_gateway=ConfirmationGateway(),
    )

    response = await gateway.check(_request())

    assert response.kind is PermissionResponseKind.ALLOW
    assert response.reason == "session_allow"


@pytest.mark.anyio
async def test_permission_gateway_records_always_session_choice_in_cache():
    settings = _FakeSettingsService()
    cache = SessionAllowCache()
    gateway = PermissionGateway(
        allow_store=AllowStore(settings),
        session_cache=cache,
        confirmation_gateway=ConfirmationGateway(),
    )

    response = await gateway.record_choice(_request(), PermissionChoice.ALWAYS_SESSION)

    assert response.kind is PermissionResponseKind.ALLOW
    assert response.reason == "always_session"
    assert cache.contains("session-1", "global:write_file:abc12345")
    assert settings.values == {}


@pytest.mark.anyio
async def test_permission_gateway_records_always_persist_after_store_write_succeeds():
    settings = _FakeSettingsService()
    gateway = PermissionGateway(
        allow_store=AllowStore(settings),
        session_cache=SessionAllowCache(),
        confirmation_gateway=ConfirmationGateway(),
    )

    response = await gateway.record_choice(_request(), PermissionChoice.ALWAYS_PERSIST)

    assert response.kind is PermissionResponseKind.ALLOW
    assert response.reason == "always_persist"
    assert settings.values == {
        "permissions.user_local.global.allow.global:write_file:abc12345": "true"
    }


@pytest.mark.anyio
async def test_permission_gateway_fails_closed_when_persist_write_fails():
    settings = _FakeSettingsService()
    settings.raise_on_set = True
    gateway = PermissionGateway(
        allow_store=AllowStore(settings),
        session_cache=SessionAllowCache(),
        confirmation_gateway=ConfirmationGateway(),
    )

    response = await gateway.record_choice(_request(), PermissionChoice.ALWAYS_PERSIST)

    assert response.kind is PermissionResponseKind.DENY
    assert response.reason == "permission_store_write_failed"
    assert settings.values == {}


@pytest.mark.anyio
async def test_permission_gateway_treats_store_read_failure_as_confirmation_miss():
    settings = _FakeSettingsService()
    settings.raise_on_get = True
    gateway = PermissionGateway(
        allow_store=AllowStore(settings),
        session_cache=SessionAllowCache(),
        confirmation_gateway=ConfirmationGateway(),
    )

    response = await gateway.check(_request())

    assert response.kind is PermissionResponseKind.NEEDS_CONFIRMATION
    assert response.reason == "allow_not_found"


@pytest.mark.anyio
async def test_permission_gateway_normalizes_reject_with_suggestion_response():
    gateway = PermissionGateway(
        allow_store=AllowStore(_FakeSettingsService()),
        session_cache=SessionAllowCache(),
        confirmation_gateway=ConfirmationGateway(),
    )

    response = await gateway.record_choice(
        _request(),
        {"response": "reject", "suggestion": "Use a read-only path instead."},
    )

    assert response.kind is PermissionResponseKind.REJECT_WITH_SUGGESTION
    assert response.rejection is not None
    assert response.rejection.suggestion == "Use a read-only path instead."
