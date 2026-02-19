import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest

from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.domain.value_objects.processing_stage import ProcessingStage
from newbee_notebook.infrastructure.tasks import document_tasks


@dataclass
class _FakeDoc:
    status: DocumentStatus
    content_path: str | None = None


class _FakeSession:
    def __init__(self):
        self.commit_calls = 0
        self.rollback_calls = 0

    async def commit(self):
        self.commit_calls += 1

    async def rollback(self):
        self.rollback_calls += 1


class _FakeDB:
    def __init__(self, session: _FakeSession):
        self._session = session

    @asynccontextmanager
    async def session(self):
        yield self._session


def test_acquire_pipeline_lock_skip_when_already_held(monkeypatch):
    class _FakeRedis:
        def set(self, **kwargs):  # noqa: ARG002
            return False

    def _fake_client():
        return _FakeRedis()

    monkeypatch.setattr(document_tasks, "_get_pipeline_lock_client", _fake_client)

    lock_key, lock_token, should_run = asyncio.run(
        document_tasks._acquire_pipeline_lock(document_id="doc-1", mode="convert_only")
    )

    assert lock_key == "newbee:notebook:document_pipeline:doc-1"
    assert lock_token is None
    assert should_run is False


def test_release_pipeline_lock_with_sync_client(monkeypatch):
    state = {"released": False}

    class _FakeRedis:
        def eval(self, script, keys_count, lock_key, lock_token):  # noqa: ARG002
            if lock_key == "lock-key" and lock_token == "lock-token":
                state["released"] = True
            return 1

    monkeypatch.setattr(document_tasks, "_get_pipeline_lock_client", lambda: _FakeRedis())

    asyncio.run(document_tasks._release_pipeline_lock("lock-key", "lock-token"))

    assert state["released"] is True


def test_acquire_pipeline_lock_across_multiple_event_loops(monkeypatch):
    class _FakeRedis:
        def __init__(self):
            self.calls = 0

        def set(self, **kwargs):  # noqa: ARG002
            self.calls += 1
            return True

    fake_client = _FakeRedis()
    monkeypatch.setattr(document_tasks, "_get_pipeline_lock_client", lambda: fake_client)

    first = asyncio.run(
        document_tasks._acquire_pipeline_lock(document_id="doc-1", mode="convert_only")
    )
    second = asyncio.run(
        document_tasks._acquire_pipeline_lock(document_id="doc-2", mode="index_only")
    )

    assert first[2] is True
    assert second[2] is True
    assert fake_client.calls == 2


def test_execute_pipeline_reraises_after_failed_status_written(monkeypatch):
    session = _FakeSession()
    fake_db = _FakeDB(session)
    state = {"failed_written": False}

    class _FakeRepo:
        def __init__(self, _session):  # noqa: ARG002
            pass

        async def get(self, document_id: str):  # noqa: ARG002
            return _FakeDoc(status=DocumentStatus.UPLOADED, content_path=None)

        async def claim_processing(self, **kwargs):  # noqa: ARG002
            return True

        async def update_status(self, **kwargs):
            if kwargs.get("status") == DocumentStatus.FAILED:
                state["failed_written"] = True

    async def _fake_get_database():
        return fake_db

    async def _fake_acquire_pipeline_lock(document_id: str, mode: str):  # noqa: ARG001
        return "lock-key", "lock-token", True

    async def _fake_release_pipeline_lock(lock_key: str | None, lock_token: str | None):  # noqa: ARG001
        return None

    async def _boom(_ctx):  # noqa: ARG001
        raise RuntimeError("boom")

    monkeypatch.setattr(document_tasks, "DocumentRepositoryImpl", _FakeRepo)
    monkeypatch.setattr(document_tasks, "get_database", _fake_get_database)
    monkeypatch.setattr(document_tasks, "_acquire_pipeline_lock", _fake_acquire_pipeline_lock)
    monkeypatch.setattr(document_tasks, "_release_pipeline_lock", _fake_release_pipeline_lock)

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(
            document_tasks._execute_pipeline(
                document_id="doc-1",
                mode="full_pipeline",
                from_statuses=[DocumentStatus.UPLOADED],
                initial_stage=ProcessingStage.QUEUED,
                pipeline_fn=_boom,
                skip_if_status=None,
            )
        )

    assert state["failed_written"] is True
    assert session.rollback_calls == 1
