import asyncio

import pytest

from newbee_notebook.core.session.lock_manager import SessionLockManager


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_lock_manager_serializes_same_session_id():
    manager = SessionLockManager()
    events: list[str] = []

    async def worker(name: str):
        async with manager.acquire("session-1"):
            events.append(f"start:{name}")
            await asyncio.sleep(0.01)
            events.append(f"end:{name}")

    first = asyncio.create_task(worker("a"))
    await asyncio.sleep(0)
    second = asyncio.create_task(worker("b"))
    await asyncio.gather(first, second)

    assert events == ["start:a", "end:a", "start:b", "end:b"]


@pytest.mark.anyio
async def test_lock_manager_allows_different_session_ids():
    manager = SessionLockManager()
    entered = asyncio.Event()
    can_exit = asyncio.Event()
    events: list[str] = []

    async def first_worker():
        async with manager.acquire("session-1"):
            events.append("start:a")
            entered.set()
            await can_exit.wait()
            events.append("end:a")

    async def second_worker():
        await entered.wait()
        async with manager.acquire("session-2"):
            events.append("start:b")
            events.append("end:b")
            can_exit.set()

    await asyncio.gather(first_worker(), second_worker())

    assert events[:3] == ["start:a", "start:b", "end:b"]
