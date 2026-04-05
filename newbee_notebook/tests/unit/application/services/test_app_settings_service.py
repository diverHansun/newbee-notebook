import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy.dialects import postgresql

from newbee_notebook.application.services.app_settings_service import AppSettingsService


def test_get_returns_value_or_none():
    session = AsyncMock()
    service = AppSettingsService(session)

    result = SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(value="qwen"))
    session.execute.return_value = result

    assert asyncio.run(service.get("llm.provider")) == "qwen"

    result = SimpleNamespace(scalar_one_or_none=lambda: None)
    session.execute.return_value = result
    assert asyncio.run(service.get("llm.provider")) is None


def test_get_many_returns_prefixed_dict():
    session = AsyncMock()
    service = AppSettingsService(session)

    rows = [
        SimpleNamespace(key="llm.provider", value="qwen"),
        SimpleNamespace(key="llm.model", value="qwen3.5-plus"),
    ]
    result = SimpleNamespace(scalars=lambda: rows)
    session.execute.return_value = result

    got = asyncio.run(service.get_many("llm."))
    assert got == {
        "llm.provider": "qwen",
        "llm.model": "qwen3.5-plus",
    }


def test_set_uses_upsert_statement():
    session = AsyncMock()
    service = AppSettingsService(session)

    asyncio.run(service.set("llm.provider", "zhipu"))

    stmt = session.execute.call_args.args[0]
    sql = str(
        stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "ON CONFLICT" in sql
    assert "app_settings" in sql


def test_set_many_calls_set_for_each_item(monkeypatch):
    session = AsyncMock()
    service = AppSettingsService(session)
    set_mock = AsyncMock()
    monkeypatch.setattr(service, "set", set_mock)

    asyncio.run(
        service.set_many(
            {
                "llm.provider": "qwen",
                "llm.model": "qwen3.5-plus",
            }
        )
    )

    assert set_mock.await_count == 2


def test_delete_executes_delete_statement():
    session = AsyncMock()
    service = AppSettingsService(session)

    asyncio.run(service.delete("llm.provider"))
    session.execute.assert_awaited_once()


def test_delete_prefix_executes_delete_statement():
    session = AsyncMock()
    service = AppSettingsService(session)

    asyncio.run(service.delete_prefix("llm."))
    session.execute.assert_awaited_once()
