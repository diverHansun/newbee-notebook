"""Persist or materialize user permission choices."""

from __future__ import annotations

from typing import Any

from newbee_notebook.core.permission.allow_store import AllowStore
from newbee_notebook.core.permission.contracts import (
    PermissionChoice,
    PermissionRequest,
    PermissionResponse,
    normalize_permission_choice,
)
from newbee_notebook.core.permission.session_cache import SessionAllowCache


class DecisionRecorder:
    def __init__(
        self,
        *,
        allow_store: AllowStore,
        session_cache: SessionAllowCache,
    ) -> None:
        self._allow_store = allow_store
        self._session_cache = session_cache

    async def record(self, request: PermissionRequest, choice: Any) -> PermissionResponse:
        normalized_choice, suggestion = normalize_permission_choice(choice)
        if normalized_choice is PermissionChoice.ONCE:
            return PermissionResponse.allow(reason="once")
        if normalized_choice is PermissionChoice.ALWAYS_SESSION:
            self._session_cache.add_all(request.session_id)
            return PermissionResponse.allow(reason="always_session")
        if normalized_choice is PermissionChoice.ALWAYS_PERSIST:
            try:
                await self._allow_store.write(request.capability_signature)
            except Exception:
                return PermissionResponse.deny(reason="permission_store_write_failed")
            self._session_cache.add_all(request.session_id)
            return PermissionResponse.allow(reason="always_persist")
        if normalized_choice is PermissionChoice.REJECT_WITH_SUGGESTION:
            return PermissionResponse.reject_with_suggestion(
                capability_signature=request.capability_signature,
                suggestion=suggestion,
            )
        return PermissionResponse.deny(reason="user_rejected")
