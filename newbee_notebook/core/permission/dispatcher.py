"""Confirmation gateway adapter for permission choices."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from newbee_notebook.core.permission.contracts import PermissionChoice, normalize_permission_choice

if TYPE_CHECKING:
    from newbee_notebook.core.engine.confirmation import ConfirmationGateway


class ConfirmationDispatcher:
    def __init__(self, confirmation_gateway: ConfirmationGateway | None = None) -> None:
        self._confirmation_gateway = confirmation_gateway

    def create(self, request_id: str) -> bool:
        if self._confirmation_gateway is None:
            return False
        self._confirmation_gateway.create(request_id)
        return True

    async def wait_for_choice(
        self,
        request_id: str,
        *,
        timeout: float = 180.0,
    ) -> PermissionChoice | dict[str, Any]:
        if self._confirmation_gateway is None:
            return PermissionChoice.REJECT
        response = await self._confirmation_gateway.wait_response(request_id, timeout=timeout)
        if isinstance(response, dict):
            return response
        return normalize_permission_choice(response)[0]
