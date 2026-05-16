from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from newbee_notebook.infrastructure.tasks import document_tasks

pytestmark = pytest.mark.unit


def test_prepare_mineru_runtime_for_conversion_syncs_db_config_then_title_aided(monkeypatch):
    mineru_config = {
        "mode": "local",
        "local_enabled": True,
        "title_aided_enabled": True,
    }
    sync_mock = AsyncMock(return_value=mineru_config)
    prepare_mock = AsyncMock()

    monkeypatch.setattr(document_tasks, "sync_mineru_runtime_env_from_db", sync_mock)
    monkeypatch.setattr(
        document_tasks,
        "prepare_mineru_title_aided_runtime_from_session",
        prepare_mock,
    )

    asyncio.run(document_tasks._prepare_mineru_runtime_for_conversion(object()))

    sync_mock.assert_awaited_once()
    prepare_mock.assert_awaited_once()
    assert prepare_mock.await_args.args[1] == mineru_config


def test_prepare_mineru_runtime_for_conversion_continues_when_title_aided_write_fails(monkeypatch):
    mineru_config = {
        "mode": "local",
        "local_enabled": True,
        "title_aided_enabled": True,
    }
    sync_mock = AsyncMock(return_value=mineru_config)
    prepare_mock = AsyncMock(side_effect=OSError("runtime config volume is read-only"))

    monkeypatch.setattr(document_tasks, "sync_mineru_runtime_env_from_db", sync_mock)
    monkeypatch.setattr(
        document_tasks,
        "prepare_mineru_title_aided_runtime_from_session",
        prepare_mock,
    )

    result = asyncio.run(document_tasks._prepare_mineru_runtime_for_conversion(object()))

    assert result == mineru_config
    sync_mock.assert_awaited_once()
    prepare_mock.assert_awaited_once()
