from __future__ import annotations

import pytest


class _FakeSettingsService:
    def __init__(self, values: dict[str, str]):
        self._values = values

    async def get_many(self, prefix: str):
        return {key: value for key, value in self._values.items() if key.startswith(prefix)}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_get_asr_config_async_prefers_db_values(monkeypatch):
    from newbee_notebook.core.common import config_db

    values = {
        "asr.provider": "qwen",
        "asr.model": "qwen3-asr-flash",
    }
    monkeypatch.setattr(
        config_db,
        "_get_app_settings_service",
        lambda _session: _FakeSettingsService(values),
    )
    monkeypatch.delenv("ASR_PROVIDER", raising=False)
    monkeypatch.delenv("ASR_MODEL", raising=False)

    payload = await config_db.get_asr_config_async(object())

    assert payload == {
        "provider": "qwen",
        "model": "qwen3-asr-flash",
        "source": "db",
    }


@pytest.mark.anyio
async def test_get_asr_config_async_uses_env_and_provider_default_model(monkeypatch):
    from newbee_notebook.core.common import config_db

    monkeypatch.setattr(
        config_db,
        "_get_app_settings_service",
        lambda _session: _FakeSettingsService({}),
    )
    monkeypatch.setenv("ASR_PROVIDER", "qwen")
    monkeypatch.delenv("ASR_MODEL", raising=False)

    payload = await config_db.get_asr_config_async(object())

    assert payload == {
        "provider": "qwen",
        "model": "qwen3-asr-flash",
        "source": "env",
    }


def test_resolve_asr_api_key_reuses_provider_keys(monkeypatch):
    from newbee_notebook.core.common.config_db import resolve_asr_api_key

    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")

    assert resolve_asr_api_key("zhipu") == "zhipu-key"
    assert resolve_asr_api_key("qwen") == "dashscope-key"
    assert resolve_asr_api_key("unknown") is None
