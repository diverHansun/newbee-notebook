from __future__ import annotations

from pathlib import Path

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_compose(filename: str) -> dict:
    compose_path = _repo_root() / filename
    return yaml.safe_load(compose_path.read_text(encoding="utf-8"))


def test_default_compose_starts_full_non_gpu_stack() -> None:
    compose = _load_compose("docker-compose.yml")
    services = compose["services"]

    expected_services = {
        "redis",
        "postgres",
        "elasticsearch",
        "minio",
        "celery-worker",
        "api",
        "frontend",
    }

    assert expected_services.issubset(set(services))
    assert "mineru-api" not in services
    assert "profiles" not in services["minio"]


def test_default_compose_fixes_non_gpu_runtime_defaults() -> None:
    compose = _load_compose("docker-compose.yml")
    services = compose["services"]

    worker_env = services["celery-worker"]["environment"]
    api_env = services["api"]["environment"]

    assert worker_env["STORAGE_BACKEND"] == "minio"
    assert worker_env["MINIO_ENDPOINT"] == "${MINIO_INTERNAL_ENDPOINT:-minio:9000}"
    assert worker_env["MINERU_MODE"] == "cloud"
    assert worker_env["MINERU_LOCAL_ENABLED"] == "false"
    assert worker_env["MINERU_LOCAL_API_URL"] == "${MINERU_INTERNAL_API_URL:-http://mineru-api:8000}"
    assert worker_env["QWEN3_EMBEDDING_MODE"] == "api"

    assert api_env["STORAGE_BACKEND"] == "minio"
    assert api_env["MINIO_ENDPOINT"] == "${MINIO_INTERNAL_ENDPOINT:-minio:9000}"
    assert api_env["MINERU_MODE"] == "cloud"
    assert api_env["MINERU_LOCAL_ENABLED"] == "false"
    assert api_env["MINERU_LOCAL_API_URL"] == "${MINERU_INTERNAL_API_URL:-http://mineru-api:8000}"
    assert api_env["QWEN3_EMBEDDING_MODE"] == "api"


def test_frontend_service_uses_api_container_and_fixed_port() -> None:
    compose = _load_compose("docker-compose.yml")
    frontend = compose["services"]["frontend"]

    assert frontend["ports"] == ["3000:3000"]
    assert frontend["environment"]["INTERNAL_API_URL"] == "http://api:8000"
    assert "api" in frontend["depends_on"]


def test_gpu_override_switches_embedding_and_mineru_to_local_gpu() -> None:
    compose = _load_compose("docker-compose.gpu.yml")
    services = compose["services"]
    worker_env = services["celery-worker"]["environment"]
    api_env = services["api"]["environment"]

    assert worker_env["MINERU_MODE"] == "local"
    assert worker_env["MINERU_LOCAL_ENABLED"] == "true"
    assert worker_env["MINERU_BACKEND"] == "hybrid-auto-engine"
    assert worker_env["QWEN3_EMBEDDING_MODE"] == "local"
    assert worker_env["QWEN3_EMBEDDING_DEVICE"] == "cuda"

    assert api_env["MINERU_MODE"] == "local"
    assert api_env["MINERU_LOCAL_ENABLED"] == "true"
    assert api_env["QWEN3_EMBEDDING_MODE"] == "local"
    assert api_env["QWEN3_EMBEDDING_MODEL_PATH"] == "models/Qwen3-Embedding-0.6B"
    assert services["api"]["volumes"] == ["./models:/app/models:ro"]
    assert "mineru-api" in services
