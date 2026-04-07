from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_get_runtime_session_manager_dep_syncs_embedding_runtime(monkeypatch):
    from newbee_notebook.api import dependencies

    sync_mock = AsyncMock(return_value={"provider": "qwen3-embedding", "mode": "api"})
    monkeypatch.setattr(dependencies, "sync_embedding_runtime_env_from_db", sync_mock)

    manager = await dependencies.get_runtime_session_manager_dep(
        session_repo=AsyncMock(),
        message_repo=AsyncMock(),
        runtime_config=SimpleNamespace(provider="qwen", model="qwen3-32b"),
        llm_client=object(),
        tool_registry=object(),
        mcp_manager=object(),
        confirmation_gateway=object(),
        session=object(),
    )

    assert manager is not None
    sync_mock.assert_awaited_once()


@pytest.mark.anyio
async def test_get_chat_service_defers_pgvector_loading(monkeypatch):
    from newbee_notebook.api import dependencies

    pg_index = object()
    load_pg_index_mock = AsyncMock(return_value=pg_index)
    monkeypatch.setattr(dependencies, "get_pg_index_singleton", load_pg_index_mock)

    service = await dependencies.get_chat_service(
        session_repo=AsyncMock(),
        notebook_repo=AsyncMock(),
        reference_repo=AsyncMock(),
        document_repo=AsyncMock(),
        ref_repo=AsyncMock(),
        message_repo=AsyncMock(),
        session_manager=object(),
        skill_registry=object(),
        confirmation_gateway=object(),
    )

    load_pg_index_mock.assert_not_awaited()
    assert await service._get_vector_index() is pg_index
    load_pg_index_mock.assert_awaited_once()