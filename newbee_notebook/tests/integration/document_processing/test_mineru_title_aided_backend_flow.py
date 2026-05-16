from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.integration


class _FakeSettingsService:
    def __init__(self, values: dict[str, str]):
        self._values = values

    async def get_many(self, prefix: str):
        return {key: value for key, value in self._values.items() if key.startswith(prefix)}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_local_title_aided_backend_flow_writes_runtime_json_from_chat_llm_config(
    monkeypatch,
    tmp_path,
):
    from newbee_notebook.core.common import config_db
    from newbee_notebook.infrastructure.document_processing.mineru_title_aided import (
        prepare_mineru_title_aided_runtime_from_session,
    )

    values = {
        "mineru.mode": "local",
        "mineru.title_aided_enabled": "true",
        "llm.provider": "zhipu",
        "llm.model": "glm-5v-turbo",
        "llm.temperature": "0.7",
        "llm.max_tokens": "32768",
        "llm.top_p": "0.8",
    }
    runtime_path = tmp_path / "mineru-runtime.json"
    monkeypatch.setattr(
        config_db,
        "_get_app_settings_service",
        lambda _session: _FakeSettingsService(values),
    )
    monkeypatch.setattr(
        config_db,
        "_BOOTSTRAP_ENV",
        {
            "MINERU_LOCAL_ENABLED": "true",
        },
        raising=False,
    )
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-secret")
    monkeypatch.setenv("MINERU_TITLE_AIDED_CONFIG_PATH", str(runtime_path))

    mineru_config = await config_db.get_mineru_config_async(object())
    result = await prepare_mineru_title_aided_runtime_from_session(object(), mineru_config)

    assert result.status == "enabled"
    payload = json.loads(runtime_path.read_text(encoding="utf-8"))
    assert payload == {
        "llm-aided-config": {
            "title_aided": {
                "enable": True,
                "model": "glm-5v-turbo",
                "api_key": "zhipu-secret",
                "base_url": "https://open.bigmodel.cn/api/paas/v4",
            }
        }
    }


def test_runtime_config_writer_replaces_existing_file_atomically(monkeypatch, tmp_path):
    from newbee_notebook.infrastructure.document_processing import mineru_title_aided

    runtime_path = tmp_path / "mineru-runtime.json"
    runtime_path.write_text(
        json.dumps(
            {
                "llm-aided-config": {
                    "title_aided": {
                        "enable": True,
                        "model": "old-model",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MINERU_TITLE_AIDED_CONFIG_PATH", str(runtime_path))

    mineru_title_aided.write_mineru_title_aided_runtime_config(
        {
            "llm-aided-config": {
                "title_aided": {
                    "enable": False,
                }
            }
        }
    )

    payload = json.loads(runtime_path.read_text(encoding="utf-8"))
    assert payload["llm-aided-config"]["title_aided"] == {"enable": False}
    assert not list(tmp_path.glob("*.tmp"))


def test_runtime_config_writer_keeps_existing_file_when_replace_fails(monkeypatch, tmp_path):
    from newbee_notebook.infrastructure.document_processing import mineru_title_aided

    runtime_path = tmp_path / "mineru-runtime.json"
    runtime_path.write_text('{"stable": true}', encoding="utf-8")
    monkeypatch.setenv("MINERU_TITLE_AIDED_CONFIG_PATH", str(runtime_path))

    def _raise_replace(_src, _dst):
        raise OSError("replace failed")

    monkeypatch.setattr(mineru_title_aided.os, "replace", _raise_replace)

    with pytest.raises(OSError):
        mineru_title_aided.write_mineru_title_aided_runtime_config(
            {
                "llm-aided-config": {
                    "title_aided": {
                        "enable": False,
                    }
                }
            }
        )

    assert runtime_path.read_text(encoding="utf-8") == '{"stable": true}'
    assert not list(tmp_path.glob("*.tmp"))
