from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.smoke


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_compose(filename: str) -> dict:
    compose_path = _repo_root() / filename
    return yaml.safe_load(compose_path.read_text(encoding="utf-8"))


def _load_merged_gpu_compose() -> dict:
    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                "docker-compose.yml",
                "-f",
                "docker-compose.gpu.yml",
                "config",
                "--format",
                "json",
            ],
            cwd=_repo_root(),
            text=True,
            capture_output=True,
            check=True,
        )
    except FileNotFoundError:
        pytest.skip("docker CLI is not available")
    return json.loads(result.stdout)


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
    assert "./models:/app/models:ro" in services["api"]["volumes"]
    assert "mineru-api" in services


def test_gpu_override_shares_mineru_title_aided_runtime_config() -> None:
    compose = _load_compose("docker-compose.gpu.yml")
    services = compose["services"]

    worker = services["celery-worker"]
    api = services["api"]
    mineru_api = services["mineru-api"]

    runtime_path = "/app/data/mineru/mineru-runtime.json"
    assert worker["environment"]["MINERU_TITLE_AIDED_CONFIG_PATH"] == runtime_path
    assert api["environment"]["MINERU_TITLE_AIDED_CONFIG_PATH"] == runtime_path
    assert "./data/mineru:/app/data/mineru" in worker["volumes"]
    assert "./data/mineru:/app/data/mineru" in api["volumes"]

    assert (
        mineru_api["environment"]["NEWBEE_MINERU_TITLE_AIDED_CONFIG_JSON"]
        == "/root/mineru-runtime/mineru-runtime.json"
    )
    assert "./data/mineru:/root/mineru-runtime:ro" in mineru_api["volumes"]
    assert mineru_api["environment"]["MINERU_API_MAX_CONCURRENT_REQUESTS"] == "${MINERU_API_MAX_CONCURRENT_REQUESTS:-1}"


def test_mineru_gpu_dockerfile_applies_title_aided_runtime_adapter() -> None:
    dockerfile = (_repo_root() / "docker/mineru/Dockerfile.gpu").read_text(encoding="utf-8")

    assert "FROM mineru:latest" in dockerfile
    assert "mineru[core]==" not in dockerfile
    assert "patches/apply_title_aided_runtime_patch.py" in dockerfile
    assert "python3 /tmp/mineru-patches/apply_title_aided_runtime_patch.py" in dockerfile


def test_mineru_gpu_patch_files_are_not_gitignored() -> None:
    patch_path = "docker/mineru/patches/apply_title_aided_runtime_patch.py"
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", patch_path],
            cwd=_repo_root(),
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        pytest.skip("git CLI is not available")

    assert result.returncode != 0


def test_gpu_merged_compose_preserves_base_worker_mounts_and_adds_title_runtime() -> None:
    compose = _load_merged_gpu_compose()
    services = compose["services"]

    worker = services["celery-worker"]
    api = services["api"]
    mineru_api = services["mineru-api"]

    worker_volumes = {(volume["target"], volume.get("read_only", False)) for volume in worker["volumes"]}
    api_volumes = {(volume["target"], volume.get("read_only", False)) for volume in api["volumes"]}
    mineru_volumes = {(volume["target"], volume.get("read_only", False)) for volume in mineru_api["volumes"]}

    assert ("/app", False) in worker_volumes
    assert ("/app/data/mineru", False) in worker_volumes
    assert ("/app/models", True) in api_volumes
    assert ("/app/data/mineru", False) in api_volumes
    assert ("/root/mineru-runtime", True) in mineru_volumes
    assert worker["environment"]["MINERU_TITLE_AIDED_CONFIG_PATH"] == "/app/data/mineru/mineru-runtime.json"
    assert api["environment"]["MINERU_TITLE_AIDED_CONFIG_PATH"] == "/app/data/mineru/mineru-runtime.json"
    assert (
        mineru_api["environment"]["NEWBEE_MINERU_TITLE_AIDED_CONFIG_JSON"]
        == "/root/mineru-runtime/mineru-runtime.json"
    )
