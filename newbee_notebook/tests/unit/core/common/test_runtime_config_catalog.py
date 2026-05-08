from pathlib import Path

import pytest

from newbee_notebook.core.common import config as config_module


RUNTIME_CONFIG_FILES = {
    "document_processing.yaml",
    "embeddings.yaml",
    "llm.yaml",
    "storage.yaml",
    "zhipu_tools.yaml",
}

REMOVED_ENV_KEYS = {
    "LOG_LEVEL",
    "VERBOSE",
}


def test_runtime_config_directory_contains_only_supported_yaml_files():
    config_files = {path.name for path in config_module.CONFIG_DIR.glob("*.yaml")}

    assert config_files == RUNTIME_CONFIG_FILES


def test_env_example_only_mentions_runtime_supported_env_keys():
    env_example = Path(".env.example").read_text(encoding="utf-8")

    for key in REMOVED_ENV_KEYS:
        assert f"{key}=" not in env_example


def test_legacy_llm_model_fallback_uses_zhipu_vision_default(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "zhipu")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setattr(config_module, "get_llm_config", lambda: {})

    assert config_module.get_llm_model() == "glm-5v-turbo"
