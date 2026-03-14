import pytest

from newbee_notebook.infrastructure.persistence import database as database_module


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_get_database_reconnects_existing_disconnected_instance(monkeypatch):
    original_database = database_module._database
    original_schema_checked = database_module._schema_checked

    try:
        disconnected = database_module.Database("postgresql+asyncpg://example")
        database_module._database = disconnected
        database_module._schema_checked = True

        calls = 0

        async def fake_connect(self):
            nonlocal calls
            calls += 1
            self._engine = object()
            self._session_factory = object()

        monkeypatch.setattr(database_module.Database, "connect", fake_connect)

        db = await database_module.get_database()

        assert db is disconnected
        assert calls == 1
        assert db._session_factory is not None
    finally:
        database_module._database = original_database
        database_module._schema_checked = original_schema_checked


@pytest.mark.anyio
async def test_get_database_retries_after_failed_initial_connect(monkeypatch):
    original_database = database_module._database
    original_schema_checked = database_module._schema_checked

    try:
        database_module._database = None
        database_module._schema_checked = True

        calls = 0

        async def flaky_connect(self):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("temporary network failure")
            self._engine = object()
            self._session_factory = object()

        monkeypatch.setattr(database_module.Database, "connect", flaky_connect)

        with pytest.raises(OSError):
            await database_module.get_database()

        assert database_module._database is not None
        assert database_module._database._session_factory is None

        recovered = await database_module.get_database()

        assert calls == 2
        assert recovered._session_factory is not None
    finally:
        database_module._database = original_database
        database_module._schema_checked = original_schema_checked
