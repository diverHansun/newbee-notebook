"""Confirmation primitives for pause-and-resume tool execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class PendingConfirmation:
    event: asyncio.Event = field(default_factory=asyncio.Event)
    approved: bool = False


class ConfirmationGateway:
    def __init__(self) -> None:
        self._pending: dict[str, PendingConfirmation] = {}

    def create(self, request_id: str) -> None:
        self._pending[request_id] = PendingConfirmation()

    async def wait(self, request_id: str, timeout: float = 180.0) -> bool:
        pending = self._pending.get(request_id)
        if pending is None:
            return False
        try:
            await asyncio.wait_for(pending.event.wait(), timeout=timeout)
            return pending.approved
        except asyncio.TimeoutError:
            return False
        finally:
            self._pending.pop(request_id, None)

    def resolve(self, request_id: str, approved: bool) -> bool:
        pending = self._pending.get(request_id)
        if pending is None:
            return False
        pending.approved = approved
        pending.event.set()
        return True
