from __future__ import annotations

import json

import pytest


class _FakeSettingsService:
    def __init__(self, values: dict[str, str]):
        self._values = values
        self.set_calls: list[tuple[str, str]] = []
        self.delete_calls: list[str] = []

    async def get_many(self, prefix: str):
        return {key: value for key, value in self._values.items() if key.startswith(prefix)}

    async def get(self, key: str):
        return self._values.get(key)

    async def set(self, key: str, value: str):
        self._values[key] = value
        self.set_calls.append((key, value))

    async def delete(self, key: str):
        self._values.pop(key, None)
        self.delete_calls.append(key)


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


@pytest.mark.anyio
async def test_get_bilibili_credential_async_reads_json_blob(monkeypatch):
    from newbee_notebook.core.common import config_db

    values = {
        "bilibili.credential": json.dumps(
            {
                "sessdata": "abc",
                "bili_jct": "def",
                "buvid3": "ghi",
                "buvid4": "",
                "dedeuserid": "123",
                "ac_time_value": "token",
            }
        )
    }
    monkeypatch.setattr(
        config_db,
        "_get_app_settings_service",
        lambda _session: _FakeSettingsService(values),
    )

    payload = await config_db.get_bilibili_credential_async(object())

    assert payload == {
        "sessdata": "abc",
        "bili_jct": "def",
        "buvid3": "ghi",
        "buvid4": "",
        "dedeuserid": "123",
        "ac_time_value": "token",
    }


@pytest.mark.anyio
async def test_save_bilibili_credential_async_normalizes_payload(monkeypatch):
    from newbee_notebook.core.common import config_db

    fake_service = _FakeSettingsService({})
    monkeypatch.setattr(
        config_db,
        "_get_app_settings_service",
        lambda _session: fake_service,
    )

    await config_db.save_bilibili_credential_async(
        object(),
        {
            "sessdata": "abc",
            "bili_jct": "def",
            "unexpected": "ignored",
        },
    )

    assert fake_service.set_calls == [
        (
            "bilibili.credential",
            json.dumps(
                {
                    "sessdata": "abc",
                    "bili_jct": "def",
                    "buvid3": "",
                    "buvid4": "",
                    "dedeuserid": "",
                    "ac_time_value": "",
                },
                ensure_ascii=False,
            ),
        )
    ]


@pytest.mark.anyio
async def test_delete_bilibili_credential_async_removes_single_key(monkeypatch):
    from newbee_notebook.core.common import config_db

    fake_service = _FakeSettingsService(
        {"bilibili.credential": json.dumps({"sessdata": "abc"})}
    )
    monkeypatch.setattr(
        config_db,
        "_get_app_settings_service",
        lambda _session: fake_service,
    )

    await config_db.delete_bilibili_credential_async(object())

    assert fake_service.delete_calls == ["bilibili.credential"]
