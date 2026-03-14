from __future__ import annotations

import asyncio
from types import SimpleNamespace

from newbee_notebook.core.llm import config as llm_config_module


def test_resolve_llm_runtime_config_uses_db_model_and_provider_specific_env(monkeypatch):
    async def _fake_get_llm_config_async(_session):
        return {
            "provider": "qwen",
            "model": "qwen3.5-plus",
            "temperature": 0.3,
            "max_tokens": 4096,
            "top_p": 0.75,
            "source": "db",
        }

    monkeypatch.setattr(llm_config_module, "get_llm_config_async", _fake_get_llm_config_async)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")

    config = asyncio.run(llm_config_module.resolve_llm_runtime_config(SimpleNamespace()))

    assert config.provider == "qwen"
    assert config.model == "qwen3.5-plus"
    assert config.api_key == "dashscope-key"
    assert config.base_url == llm_config_module.DEFAULT_QWEN_BASE_URL
    assert config.temperature == 0.3
    assert config.max_tokens == 4096
    assert config.top_p == 0.75


def test_resolve_llm_runtime_config_uses_provider_specific_base_url_override(monkeypatch):
    async def _fake_get_llm_config_async(_session):
        return {
            "provider": "zhipu",
            "model": "glm-4.7",
            "temperature": 0.2,
            "max_tokens": 2048,
            "top_p": 0.7,
            "source": "db",
        }

    monkeypatch.setattr(llm_config_module, "get_llm_config_async", _fake_get_llm_config_async)
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-key")
    monkeypatch.setenv("ZHIPU_API_BASE", "https://example.zhipu.test/v4")

    config = asyncio.run(llm_config_module.resolve_llm_runtime_config(SimpleNamespace()))

    assert config.provider == "zhipu"
    assert config.model == "glm-4.7"
    assert config.api_key == "zhipu-key"
    assert config.base_url == "https://example.zhipu.test/v4"
