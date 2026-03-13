"""App-level session locks for request-scoped runtime execution."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager


class SessionLockManager:
    def __init__(self):
        self._locks: dict[str, asyncio.Lock] = {}

    @asynccontextmanager
    async def acquire(self, session_id: str):
        normalized = str(session_id).strip()
        if not normalized:
            raise ValueError("session_id is required")
        lock = self._locks.setdefault(normalized, asyncio.Lock())
        await lock.acquire()
        try:
            yield
        finally:
            lock.release()

    def cleanup(self, session_id: str) -> None:
        normalized = str(session_id).strip()
        lock = self._locks.get(normalized)
        if lock is None or lock.locked():
            return
        self._locks.pop(normalized, None)
