from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_prepare_cloud_mode_skips_without_writing_runtime():
    from newbee_notebook.infrastructure.document_processing import mineru_title_aided

    writes: list[dict] = []

    result = mineru_title_aided.prepare_mineru_title_aided_runtime(
        {"mode": "cloud", "title_aided_enabled": True},
        llm_runtime_config=SimpleNamespace(
            provider="zhipu",
            model="glm-5v-turbo",
            api_key="secret-key",
            base_url="https://open.bigmodel.cn/api/paas/v4",
        ),
        writer=writes.append,
    )

    assert result.enabled is False
    assert result.status == "skipped"
    assert result.reason == "cloud_mode"
    assert result.wrote_file is False
    assert writes == []


def test_prepare_local_disabled_overwrites_old_enabled_runtime_without_secrets():
    from newbee_notebook.infrastructure.document_processing import mineru_title_aided

    writes: list[dict] = []

    result = mineru_title_aided.prepare_mineru_title_aided_runtime(
        {"mode": "local", "title_aided_enabled": False},
        llm_runtime_config=None,
        writer=writes.append,
    )

    assert result.enabled is False
    assert result.status == "disabled"
    assert result.reason == "disabled_by_setting"
    assert result.wrote_file is True
    assert writes == [
        {
            "llm-aided-config": {
                "title_aided": {
                    "enable": False,
                }
            }
        }
    ]


def test_prepare_local_enabled_reuses_chat_llm_runtime_config():
    from newbee_notebook.infrastructure.document_processing import mineru_title_aided

    writes: list[dict] = []

    result = mineru_title_aided.prepare_mineru_title_aided_runtime(
        {"mode": "local", "title_aided_enabled": True},
        llm_runtime_config=SimpleNamespace(
            provider="zhipu",
            model="glm-5v-turbo",
            api_key="secret-key",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            temperature=0.1,
            max_tokens=1024,
            top_p=0.2,
        ),
        writer=writes.append,
    )

    assert result.enabled is True
    assert result.status == "enabled"
    assert result.reason is None
    assert result.wrote_file is True
    assert writes == [
        {
            "llm-aided-config": {
                "title_aided": {
                    "enable": True,
                    "model": "glm-5v-turbo",
                    "api_key": "secret-key",
                    "base_url": "https://open.bigmodel.cn/api/paas/v4",
                }
            }
        }
    ]


def test_prepare_local_enabled_missing_key_disables_runtime():
    from newbee_notebook.infrastructure.document_processing import mineru_title_aided

    writes: list[dict] = []

    result = mineru_title_aided.prepare_mineru_title_aided_runtime(
        {"mode": "local", "title_aided_enabled": True},
        llm_runtime_config=SimpleNamespace(
            provider="qwen",
            model="qwen3.5-plus",
            api_key="",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        writer=writes.append,
    )

    assert result.enabled is False
    assert result.status == "disabled"
    assert result.reason == "missing_llm_api_key"
    assert writes == [
        {
            "llm-aided-config": {
                "title_aided": {
                    "enable": False,
                }
            }
        }
    ]


@pytest.mark.anyio
async def test_prepare_from_session_disables_runtime_when_llm_resolver_has_no_key(monkeypatch):
    from newbee_notebook.infrastructure.document_processing import mineru_title_aided

    async def _raise_missing_key(_session):
        raise ValueError("No API key configured for provider: zhipu")

    writes: list[dict] = []
    monkeypatch.setattr(mineru_title_aided, "resolve_llm_runtime_config", _raise_missing_key)

    result = await mineru_title_aided.prepare_mineru_title_aided_runtime_from_session(
        object(),
        {"mode": "local", "title_aided_enabled": True},
        writer=writes.append,
    )

    assert result.status == "disabled"
    assert result.reason == "missing_llm_api_key"
    assert writes[0]["llm-aided-config"]["title_aided"]["enable"] is False
