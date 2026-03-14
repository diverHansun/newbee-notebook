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

    async def _db_override():
        yield object()

    llm_reset = MagicMock()
    embedding_reset = MagicMock()

    monkeypatch.setattr(config_router, "AppSettingsService", FakeSettingsService)
    monkeypatch.setattr(config_router, "get_llm_config_async", _fake_get_llm_config_async)
    monkeypatch.setattr(config_router, "get_embedding_config_async", _fake_get_embedding_config_async)
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
    assert payload["embedding"]["provider"] == "qwen3-embedding"


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


def test_get_available_models_exposes_glm_4_7_preset(monkeypatch):
    client, _store, _llm_reset, _embedding_reset = _build_client(monkeypatch)

    response = client.get("/api/v1/config/models/available")

    assert response.status_code == 200
    presets = response.json()["llm"]["presets"]
    assert {preset["name"] for preset in presets} >= {"qwen3.5-plus", "glm-4.7"}


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


def test_create_app_respects_feature_model_switch_flag(monkeypatch):
    monkeypatch.setenv("FEATURE_MODEL_SWITCH", "false")
    app = create_app()
    disabled_paths = {route.path for route in app.routes}
    assert "/api/v1/config/models" not in disabled_paths

    monkeypatch.setenv("FEATURE_MODEL_SWITCH", "true")
    app = create_app()
    enabled_paths = {route.path for route in app.routes}
    assert "/api/v1/config/models" in enabled_paths
