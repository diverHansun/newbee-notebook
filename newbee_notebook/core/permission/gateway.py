"""Permission gateway for policy ASK decisions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from newbee_notebook.core.permission.allow_store import AllowStore
from newbee_notebook.core.permission.contracts import (
    PermissionChoice,
    PermissionRequest,
    PermissionResponse,
)
from newbee_notebook.core.permission.dispatcher import ConfirmationDispatcher
from newbee_notebook.core.permission.recorder import DecisionRecorder
from newbee_notebook.core.permission.session_cache import SessionAllowCache

if TYPE_CHECKING:
    from newbee_notebook.core.engine.confirmation import ConfirmationGateway


class PermissionGateway:
    def __init__(
        self,
        *,
        allow_store: AllowStore,
        session_cache: SessionAllowCache | None = None,
        confirmation_gateway: ConfirmationGateway | None = None,
        dispatcher: ConfirmationDispatcher | None = None,
        recorder: DecisionRecorder | None = None,
    ) -> None:
        self._allow_store = allow_store
        self._session_cache = session_cache or SessionAllowCache()
        self._dispatcher = dispatcher or ConfirmationDispatcher(confirmation_gateway)
        self._recorder = recorder or DecisionRecorder(
            allow_store=allow_store,
            session_cache=self._session_cache,
        )

    async def check(self, request: PermissionRequest) -> PermissionResponse:
        if not str(request.capability_signature or "").strip():
            return PermissionResponse.deny(reason="missing_capability_signature")
        if self._session_cache.contains(request.session_id, request.capability_signature):
            return PermissionResponse.allow(reason="session_allow")
        try:
            if await self._allow_store.contains(request.capability_signature):
                return PermissionResponse.allow(reason="permanent_allow")
        except Exception:
            # DB read failures are treated as a miss, then the request enters ASK.
            pass
        return PermissionResponse.needs_confirmation(reason="allow_not_found")

    def create_confirmation(self, request_id: str) -> bool:
        return self._dispatcher.create(request_id)

    async def wait_for_choice(
        self,
        request_id: str,
        *,
        timeout: float = 180.0,
    ) -> PermissionChoice | dict[str, Any]:
        return await self._dispatcher.wait_for_choice(request_id, timeout=timeout)

    async def record_choice(
        self,
        request: PermissionRequest,
        choice: Any,
    ) -> PermissionResponse:
        return await self._recorder.record(request, choice)

    def clear_session(self, session_id: str) -> None:
        self._session_cache.clear_session(session_id)

    def reset_on_startup(self) -> None:
        self._session_cache.reset_all()

    async def clear_skill_permissions(self, skill_name: str) -> int:
        removed_persistent = await self._allow_store.delete_by_skill(skill_name)
        removed_session = self._session_cache.remove_by_skill(skill_name)
        return removed_persistent + removed_session
