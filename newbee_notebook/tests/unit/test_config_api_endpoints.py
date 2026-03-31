from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from newbee_notebook.api.dependencies import get_db_session
from newbee_notebook.api.main import create_app
from newbee_notebook.api.routers import config as config_router


def _build_client(monkeypatch):
    app = FastAPI()
    app.include_router(config_router.router, prefix="/api/v1")

    store: dict[str, str] = {}

    class FakeSettingsService:
        def __init__(self, _session):
            self._store = store

        async def get(self, key: str):
            return self._store.get(key)

        async def get_many(self, prefix: str):
            return {k: v for k, v in self._store.items() if k.startswith(prefix)}

        async def set(self, key: str, value: str):
            self._store[key] = value

        async def set_many(self, settings: dict[str, str]):
            self._store.update(settings)

        async def delete(self, key: str):
            self._store.pop(key, None)

        async def delete_prefix(self, prefix: str):
            for key in [k for k in list(self._store.keys()) if k.startswith(prefix)]:
                self._store.pop(key, None)

    async def _fake_get_llm_config_async(_session):
        return {
            "provider": store.get("llm.provider", "qwen"),
            "model": store.get("llm.model", "qwen3.5-plus"),
            "temperature": float(store.get("llm.temperature", "0.7")),
            "max_tokens": int(store.get("llm.max_tokens", "32768")),
            "top_p": float(store.get("llm.top_p", "0.8")),
            "source": "db" if "llm.provider" in store else "default",
        }

    async def _fake_get_embedding_config_async(_session):
        provider = store.get("embedding.provider", "qwen3-embedding")
        mode = store.get("embedding.mode", "api") if provider == "qwen3-embedding" else None
        model = (
            store.get("embedding.api_model", "text-embedding-v4")
            if provider == "qwen3-embedding"
            else "embedding-3"
        )
        return {
            "provider": provider,
            "mode": mode,
            "model": model,
            "dim": 1024,
            "source": "db" if "embedding.provider" in store else "default",
        }

    async def _fake_get_asr_config_async(_session):
        provider = store.get("asr.provider", "zhipu")
        model = store.get(
            "asr.model",
            "glm-asr-2512" if provider == "zhipu" else "qwen3-asr-flash",
        )
        return {
            "provider": provider,
            "model": model,
            "source": "db" if "asr.provider" in store else "default",
        }

    async def _fake_get_mineru_config_async(_session):
        local_enabled = store.get("mineru.local_enabled", "true").lower() in {"1", "true", "yes", "on"}
        mode = store.get("mineru.mode", "cloud")
        if mode == "local" and not local_enabled:
            mode = "cloud"
        return {
            "mode": mode,
            "source": "db" if "mineru.mode" in store else "default",
            "local_enabled": local_enabled,
        }

    async def _db_override():
        yield object()

    llm_reset = MagicMock()
    embedding_reset = MagicMock()

    monkeypatch.setattr(config_router, "AppSettingsService", FakeSettingsService)
    monkeypatch.setattr(config_router, "get_llm_config_async", _fake_get_llm_config_async)
    monkeypatch.setattr(config_router, "get_embedding_config_async", _fake_get_embedding_config_async)
    monkeypatch.setattr(config_router, "get_asr_config_async", _fake_get_asr_config_async)
    monkeypatch.setattr(config_router, "get_mineru_config_async", _fake_get_mineru_config_async)
    monkeypatch.setattr(
        config_router,
        "resolve_asr_api_key",
        lambda provider: "configured-key" if provider in {"zhipu", "qwen"} else None,
    )
    monkeypatch.setattr(
        config_router,
        "resolve_llm_api_key",
        lambda provider: "configured-key" if provider in {"zhipu", "qwen"} else None,
    )
    monkeypatch.setattr(config_router, "_NOT_APPLICABLE", "__not_applicable__", raising=False)
    monkeypatch.setattr(
        config_router,
        "resolve_embedding_api_key",
        lambda provider, mode: (
            "__not_applicable__"
            if provider == "qwen3-embedding" and str(mode or "").strip().lower() == "local"
            else ("configured-key" if provider in {"qwen3-embedding", "zhipu"} else None)
        ),
    )
    monkeypatch.setattr(
        config_router,
        "resolve_mineru_api_key",
        lambda mode: "__not_applicable__" if str(mode or "").strip().lower() == "local" else "configured-key",
    )
    monkeypatch.setattr(config_router, "get_registered_llm_providers", lambda: ["qwen", "zhipu"])
    monkeypatch.setattr(
        config_router,
        "get_registered_embedding_providers",
        lambda: ["qwen3-embedding", "zhipu"],
    )
    monkeypatch.setattr(config_router, "reset_llm_singleton", llm_reset)
    monkeypatch.setattr(config_router, "reset_embedding_singleton", embedding_reset)

    app.dependency_overrides[get_db_session] = _db_override

    return TestClient(app), store, llm_reset, embedding_reset


def test_get_models_returns_effective_config(monkeypatch):
    client, _store, _llm_reset, _embedding_reset = _build_client(monkeypatch)

    response = client.get("/api/v1/config/models")
    assert response.status_code == 200
    payload = response.json()
    assert payload["llm"]["provider"] == "qwen"
    assert payload["llm"]["api_key_set"] is True
    assert payload["embedding"]["provider"] == "qwen3-embedding"
    assert payload["embedding"]["api_key_set"] is True
    assert payload["mineru"]["mode"] == "cloud"
    assert payload["mineru"]["local_enabled"] is True
    assert payload["mineru"]["api_key_set"] is True
    assert payload["asr"]["provider"] == "zhipu"
    assert payload["asr"]["api_key_set"] is True


def test_get_models_returns_null_api_key_status_for_local_modes(monkeypatch):
    client, store, _llm_reset, _embedding_reset = _build_client(monkeypatch)
    store["embedding.mode"] = "local"
    store["mineru.mode"] = "local"

    response = client.get("/api/v1/config/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload["embedding"]["mode"] == "local"
    assert payload["embedding"]["api_key_set"] is None
    assert payload["mineru"]["mode"] == "local"
    assert payload["mineru"]["api_key_set"] is None


def test_put_llm_rejects_unknown_provider(monkeypatch):
    client, _store, _llm_reset, _embedding_reset = _build_client(monkeypatch)

    response = client.put(
        "/api/v1/config/llm",
        json={
            "provider": "unknown-provider",
            "model": "x-model",
        },
    )
    assert response.status_code == 400


def test_put_llm_updates_store_and_resets_singleton(monkeypatch):
    client, store, llm_reset, _embedding_reset = _build_client(monkeypatch)

    response = client.put(
        "/api/v1/config/llm",
        json={
            "provider": "zhipu",
            "model": "glm-4.7",
            "temperature": 0.5,
            "max_tokens": 2048,
            "top_p": 0.9,
        },
    )
    assert response.status_code == 200
    assert store["llm.provider"] == "zhipu"
    assert store["llm.model"] == "glm-4.7"
    llm_reset.assert_called_once()


def test_get_available_models_exposes_glm_5_preset(monkeypatch):
    client, _store, _llm_reset, _embedding_reset = _build_client(monkeypatch)

    response = client.get("/api/v1/config/models/available")

    assert response.status_code == 200
    presets = response.json()["llm"]["presets"]
    assert {preset["name"] for preset in presets} >= {"qwen3.5-plus", "glm-5"}
    assert response.json()["mineru"]["modes"] == ["cloud", "local"]
    assert response.json()["asr"]["providers"] == ["zhipu", "qwen"]
    assert {preset["name"] for preset in response.json()["asr"]["presets"]} == {
        "glm-asr-2512",
        "qwen3-asr-flash",
    }


def test_get_available_models_limits_mineru_to_cloud_when_local_disabled(monkeypatch):
    client, store, _llm_reset, _embedding_reset = _build_client(monkeypatch)
    store["mineru.local_enabled"] = "false"

    response = client.get("/api/v1/config/models/available")

    assert response.status_code == 200
    assert response.json()["mineru"]["modes"] == ["cloud"]


def test_get_available_models_reads_local_models_from_repo_models_dir(monkeypatch, tmp_path):
    client, _store, _llm_reset, _embedding_reset = _build_client(monkeypatch)
    models_dir = tmp_path / "models"
    model_dir = models_dir / "Qwen3-Embedding-0.6B"
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(config_router, "get_models_directory", lambda: models_dir)

    response = client.get("/api/v1/config/models/available")

    assert response.status_code == 200
    assert response.json()["embedding"]["local_models"] == ["Qwen3-Embedding-0.6B"]


def test_put_embedding_rejects_invalid_mode(monkeypatch):
    client, _store, _llm_reset, _embedding_reset = _build_client(monkeypatch)

    response = client.put(
        "/api/v1/config/embedding",
        json={
            "provider": "qwen3-embedding",
            "mode": "bad-mode",
        },
    )
    assert response.status_code == 400


def test_reset_embedding_clears_prefix_and_resets_singleton(monkeypatch):
    client, store, _llm_reset, embedding_reset = _build_client(monkeypatch)

    store["embedding.provider"] = "zhipu"
    store["embedding.mode"] = "api"

    response = client.post("/api/v1/config/embedding/reset")
    assert response.status_code == 200
    assert "embedding.provider" not in store
    assert "embedding.mode" not in store
    embedding_reset.assert_called_once()


def test_put_asr_rejects_unknown_provider(monkeypatch):
    client, _store, _llm_reset, _embedding_reset = _build_client(monkeypatch)

    response = client.put(
        "/api/v1/config/asr",
        json={
            "provider": "unknown-provider",
            "model": "x-asr",
        },
    )

    assert response.status_code == 400


def test_put_asr_rejects_missing_api_key(monkeypatch):
    client, _store, _llm_reset, _embedding_reset = _build_client(monkeypatch)
    monkeypatch.setattr(config_router, "resolve_asr_api_key", lambda _provider: None)

    response = client.put(
        "/api/v1/config/asr",
        json={
            "provider": "zhipu",
            "model": "glm-asr-2512",
        },
    )

    assert response.status_code == 400


def test_put_asr_updates_store(monkeypatch):
    client, store, _llm_reset, _embedding_reset = _build_client(monkeypatch)

    response = client.put(
        "/api/v1/config/asr",
        json={
            "provider": "qwen",
            "model": "qwen3-asr-flash",
        },
    )

    assert response.status_code == 200
    assert store["asr.provider"] == "qwen"
    assert store["asr.model"] == "qwen3-asr-flash"
    assert response.json()["api_key_set"] is True


def test_put_mineru_updates_store(monkeypatch):
    client, store, _llm_reset, _embedding_reset = _build_client(monkeypatch)

    response = client.put(
        "/api/v1/config/mineru",
        json={"mode": "local"},
    )

    assert response.status_code == 200
    assert store["mineru.mode"] == "local"
    assert response.json()["mode"] == "local"


def test_put_mineru_rejects_local_when_disabled(monkeypatch):
    client, store, _llm_reset, _embedding_reset = _build_client(monkeypatch)
    store["mineru.local_enabled"] = "false"

    response = client.put(
        "/api/v1/config/mineru",
        json={"mode": "local"},
    )

    assert response.status_code == 400


def test_reset_mineru_clears_prefix(monkeypatch):
    client, store, _llm_reset, _embedding_reset = _build_client(monkeypatch)
    store["mineru.mode"] = "local"

    response = client.post("/api/v1/config/mineru/reset")

    assert response.status_code == 200
    assert "mineru.mode" not in store


def test_reset_asr_clears_prefix(monkeypatch):
    client, store, _llm_reset, _embedding_reset = _build_client(monkeypatch)

    store["asr.provider"] = "qwen"
    store["asr.model"] = "qwen3-asr-flash"

    response = client.post("/api/v1/config/asr/reset")

    assert response.status_code == 200
    assert "asr.provider" not in store
    assert "asr.model" not in store


def test_create_app_respects_feature_model_switch_flag(monkeypatch):
    monkeypatch.setenv("FEATURE_MODEL_SWITCH", "false")
    app = create_app()
    disabled_paths = {route.path for route in app.routes}
    assert "/api/v1/config/models" not in disabled_paths

    monkeypatch.setenv("FEATURE_MODEL_SWITCH", "true")
    app = create_app()
    enabled_paths = {route.path for route in app.routes}
    assert "/api/v1/config/models" in enabled_paths
