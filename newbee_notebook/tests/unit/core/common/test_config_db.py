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


@pytest.mark.anyio
async def test_get_embedding_config_async_defaults_to_api_mode(monkeypatch):
    from newbee_notebook.core.common import config_db

    monkeypatch.setattr(
        config_db,
        "_get_app_settings_service",
        lambda _session: _FakeSettingsService({}),
    )
    monkeypatch.setattr(config_db, "_BOOTSTRAP_ENV", {}, raising=False)
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("QWEN3_EMBEDDING_MODE", raising=False)
    monkeypatch.delenv("QWEN3_EMBEDDING_API_MODEL", raising=False)
    monkeypatch.delenv("QWEN3_EMBEDDING_MODEL_PATH", raising=False)

    payload = await config_db.get_embedding_config_async(object())

    assert payload["provider"] == "qwen3-embedding"
    assert payload["mode"] == "api"
    assert payload["model"] == "text-embedding-v4"
    assert payload["api_model"] == "text-embedding-v4"
    assert payload["model_path"] is None


@pytest.mark.anyio
async def test_get_embedding_config_async_prefers_bootstrap_env_over_mutated_runtime_env(monkeypatch):
    from newbee_notebook.core.common import config_db

    monkeypatch.setattr(
        config_db,
        "_get_app_settings_service",
        lambda _session: _FakeSettingsService({}),
    )
    monkeypatch.setattr(
        config_db,
        "_BOOTSTRAP_ENV",
        {
            "EMBEDDING_PROVIDER": "qwen3-embedding",
            "QWEN3_EMBEDDING_MODE": "local",
            "QWEN3_EMBEDDING_MODEL_PATH": "models/Qwen3-Embedding-0.6B",
        },
        raising=False,
    )
    monkeypatch.setenv("EMBEDDING_PROVIDER", "qwen3-embedding")
    monkeypatch.setenv("QWEN3_EMBEDDING_MODE", "api")
    monkeypatch.setenv("QWEN3_EMBEDDING_API_MODEL", "text-embedding-v4")

    payload = await config_db.get_embedding_config_async(object())

    assert payload["provider"] == "qwen3-embedding"
    assert payload["mode"] == "local"
    assert payload["model"] == "Qwen3-Embedding-0.6B"
    assert str(payload["model_path"]).endswith("models\\Qwen3-Embedding-0.6B")


@pytest.mark.anyio
async def test_get_embedding_config_async_repairs_stale_qwen_api_model(monkeypatch):
    from newbee_notebook.core.common import config_db

    fake_settings = _FakeSettingsService(
        {
            "embedding.provider": "qwen3-embedding",
            "embedding.mode": "api",
            "embedding.api_model": "Qwen3-Embedding-0.6B",
        }
    )
    monkeypatch.setattr(
        config_db,
        "_get_app_settings_service",
        lambda _session: fake_settings,
    )
    monkeypatch.setattr(config_db, "_BOOTSTRAP_ENV", {}, raising=False)

    payload = await config_db.get_embedding_config_async(object())

    assert payload["provider"] == "qwen3-embedding"
    assert payload["mode"] == "api"
    assert payload["api_provider"] == "qwen"
    assert payload["model"] == "text-embedding-v4"
    assert payload["api_model"] == "text-embedding-v4"
    assert fake_settings.set_calls == [
        ("embedding.api_provider", "qwen"),
        ("embedding.api_model", "text-embedding-v4"),
    ]


@pytest.mark.anyio
async def test_get_embedding_config_async_repairs_legacy_provider_api_model(monkeypatch):
    from newbee_notebook.core.common import config_db

    fake_settings = _FakeSettingsService(
        {
            "embedding.provider": "qwen3-embedding",
            "embedding.mode": "api",
            "embedding.api_model": "embedding-3",
        }
    )
    monkeypatch.setattr(
        config_db,
        "_get_app_settings_service",
        lambda _session: fake_settings,
    )
    monkeypatch.setattr(config_db, "_BOOTSTRAP_ENV", {}, raising=False)

    payload = await config_db.get_embedding_config_async(object())

    assert payload["provider"] == "qwen3-embedding"
    assert payload["mode"] == "api"
    assert payload["api_provider"] == "qwen"
    assert payload["model"] == "text-embedding-v4"
    assert payload["api_model"] == "text-embedding-v4"
    assert fake_settings.set_calls == [
        ("embedding.api_provider", "qwen"),
        ("embedding.api_model", "text-embedding-v4"),
    ]


@pytest.mark.anyio
async def test_get_embedding_config_async_repairs_mismatched_standard_model_with_explicit_api_provider(monkeypatch):
    from newbee_notebook.core.common import config_db

    fake_settings = _FakeSettingsService(
        {
            "embedding.provider": "qwen3-embedding",
            "embedding.mode": "api",
            "embedding.api_provider": "qwen",
            "embedding.api_model": "embedding-3",
        }
    )
    monkeypatch.setattr(
        config_db,
        "_get_app_settings_service",
        lambda _session: fake_settings,
    )
    monkeypatch.setattr(config_db, "_BOOTSTRAP_ENV", {}, raising=False)

    payload = await config_db.get_embedding_config_async(object())

    assert payload["provider"] == "qwen3-embedding"
    assert payload["mode"] == "api"
    assert payload["api_provider"] == "qwen"
    assert payload["model"] == "text-embedding-v4"
    assert payload["api_model"] == "text-embedding-v4"
    assert fake_settings.set_calls == [("embedding.api_model", "text-embedding-v4")]


@pytest.mark.anyio
async def test_get_mineru_config_async_respects_db_mode_when_local_enabled(monkeypatch):
    from newbee_notebook.core.common import config_db

    values = {"mineru.mode": "local"}
    monkeypatch.setattr(
        config_db,
        "_get_app_settings_service",
        lambda _session: _FakeSettingsService(values),
    )
    monkeypatch.setenv("MINERU_LOCAL_ENABLED", "true")

    payload = await config_db.get_mineru_config_async(object())

    assert payload == {
        "mode": "local",
        "source": "db",
        "local_enabled": True,
    }


@pytest.mark.anyio
async def test_get_mineru_config_async_forces_cloud_when_local_disabled(monkeypatch):
    from newbee_notebook.core.common import config_db

    values = {"mineru.mode": "local"}
    monkeypatch.setattr(
        config_db,
        "_get_app_settings_service",
        lambda _session: _FakeSettingsService(values),
    )
    monkeypatch.setenv("MINERU_LOCAL_ENABLED", "false")

    payload = await config_db.get_mineru_config_async(object())

    assert payload == {
        "mode": "cloud",
        "source": "db",
        "local_enabled": False,
    }


def test_resolve_asr_api_key_reuses_provider_keys(monkeypatch):
    from newbee_notebook.core.common.config_db import resolve_asr_api_key

    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")

    assert resolve_asr_api_key("zhipu") == "zhipu-key"
    assert resolve_asr_api_key("qwen") == "dashscope-key"
    assert resolve_asr_api_key("unknown") is None


def test_resolve_llm_api_key_reuses_provider_keys(monkeypatch):
    from newbee_notebook.core.common.config_db import resolve_llm_api_key

    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")

    assert resolve_llm_api_key("zhipu") == "zhipu-key"
    assert resolve_llm_api_key("qwen") == "dashscope-key"
    assert resolve_llm_api_key("unknown") is None


def test_resolve_embedding_api_key_supports_not_applicable(monkeypatch):
    from newbee_notebook.core.common.config_db import _NOT_APPLICABLE, resolve_embedding_api_key

    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")

    assert resolve_embedding_api_key("qwen3-embedding", "api") == "dashscope-key"
    assert resolve_embedding_api_key("qwen3-embedding", "local") == _NOT_APPLICABLE
    assert resolve_embedding_api_key("zhipu", None) == "zhipu-key"
    assert resolve_embedding_api_key("unknown", None) is None


def test_resolve_mineru_api_key_supports_not_applicable(monkeypatch):
    from newbee_notebook.core.common.config_db import _NOT_APPLICABLE, resolve_mineru_api_key

    monkeypatch.setenv("MINERU_API_KEY", "mineru-key")

    assert resolve_mineru_api_key("cloud") == "mineru-key"
    assert resolve_mineru_api_key("local") == _NOT_APPLICABLE


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
