"""Permission request primitives for pause-and-resume tool execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PendingPermissionRequest:
    event: asyncio.Event = field(default_factory=asyncio.Event)
    approved: bool = False
    response: Any = False


def _response_is_allowed(response: Any) -> bool:
    if isinstance(response, bool):
        return response
    if isinstance(response, str):
        return response in {"once", "always_session", "always_persist"}
    if isinstance(response, dict):
        value = response.get("approved")
        if isinstance(value, bool):
            return value
        choice = str(response.get("response") or response.get("choice") or "")
        return choice in {"once", "always_session", "always_persist"}
    return False


class PermissionRequestGateway:
    def __init__(self) -> None:
        self._pending: dict[str, PendingPermissionRequest] = {}

    def create(self, request_id: str) -> None:
        self._pending[request_id] = PendingPermissionRequest()

    async def wait(self, request_id: str, timeout: float = 180.0) -> bool:
        response = await self.wait_response(request_id, timeout=timeout)
        return _response_is_allowed(response)

    async def wait_response(self, request_id: str, timeout: float = 180.0) -> Any:
        pending = self._pending.get(request_id)
        if pending is None:
            return False
        try:
            await asyncio.wait_for(pending.event.wait(), timeout=timeout)
            return pending.response
        except asyncio.TimeoutError:
            return False
        finally:
            self._pending.pop(request_id, None)

    def resolve(self, request_id: str, approved: bool) -> bool:
        return self.resolve_response(request_id, approved)

    def resolve_response(self, request_id: str, response: Any) -> bool:
        pending = self._pending.get(request_id)
        if pending is None:
            return False
        pending.approved = _response_is_allowed(response)
        pending.response = response
        pending.event.set()
        return True
