from __future__ import annotations

import json
import os
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


def _load_merged_compose(override: str, *, profile: str | None = None) -> dict:
    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                "docker-compose.yml",
                "-f",
                override,
                *(["--profile", profile] if profile else []),
                "config",
                "--format",
                "json",
            ],
            cwd=_repo_root(),
            # PowerShell does not export PWD; do not depend on the caller's cwd.
            env={**os.environ, "NEWBEE_SANDBOX_HOST_PROJECT_ROOT": str(_repo_root())},
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


def test_default_api_loads_runtime_configs_from_host() -> None:
    api = _load_compose("docker-compose.yml")["services"]["api"]
    assert "./configs:/app/configs" in api.get("volumes", [])


def test_runtime_credentials_are_excluded_from_build_context() -> None:
    patterns = (_repo_root() / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert "configs/mcp/mcp.json" in patterns
    assert "configs/bilibili" in patterns


def test_mac_compose_uses_api_only_and_loopback_ports() -> None:
    services = _load_merged_compose("docker-compose.mac.yml")["services"]
    assert "mineru-api" not in services
    for name in ("api", "celery-worker"):
        env = services[name]["environment"]
        assert env["NEWBEE_API_ONLY"] == "true"
        assert env["MINERU_MODE"] == "cloud"
        assert env["QWEN3_EMBEDDING_MODE"] == "api"
    for service in services.values():
        for port in service.get("ports", []):
            assert port["host_ip"] == "127.0.0.1"
        assert not service.get("gpus")
    assert Path(services["minio"]["build"]["context"]).parts[-2:] == ("docker", "minio")
    api = services["api"]
    assert api["environment"]["NEWBEE_SANDBOX_HOST_PROJECT_ROOT"] == str(_repo_root())
    assert api["environment"]["NEWBEE_SANDBOX_WORK_ROOT"].startswith("/app/data/")
    assert api["environment"]["DOCKER_HOST"] == "unix:///var/run/docker.sock"
    socket_services = [
        name for name, service in services.items()
        if any(v.get("target") == "/var/run/docker.sock" for v in service.get("volumes", []))
    ]
    assert socket_services == ["api"]


def test_mac_monitor_has_isolated_image_and_internal_broker() -> None:
    services = _load_merged_compose("docker-compose.mac.yml", profile="monitor")["services"]
    assert services["flower"]["image"] != services["celery-worker"]["image"]
    assert services["flower"]["environment"]["CELERY_BROKER_URL"] == "redis://redis:6379/0"
    assert services["flower"]["build"]["args"]["INSTALL_FLOWER"] == "true"


def test_default_compose_fixes_non_gpu_runtime_defaults() -> None:
    compose = _load_compose("docker-compose.yml")
    services = compose["services"]

    worker_env = services["celery-worker"]["environment"]
    api_env = services["api"]["environment"]

    for env in (worker_env, api_env):
        assert "NEWBEE_API_ONLY" not in env
        assert "NEWBEE_SANDBOX_HOST_PROJECT_ROOT" not in env

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
    assert api_env["MINERU_BACKEND"] == "hybrid-auto-engine"
    assert api_env["QWEN3_EMBEDDING_MODE"] == "local"
    assert api_env["QWEN3_EMBEDDING_MODEL_PATH"] == "models/Qwen3-Embedding-0.6B"
    assert "./models:/app/models:ro" in services["api"]["volumes"]
    assert "mineru-api" in services


def test_gpu_override_mineru_healthcheck_uses_health_endpoint() -> None:
    compose = _load_compose("docker-compose.gpu.yml")
    healthcheck = compose["services"]["mineru-api"]["healthcheck"]["test"]
    rendered = " ".join(healthcheck)

    assert "/health" in rendered
    assert "/docs" not in rendered


def test_gpu_override_waits_for_mineru_api_health_before_api_and_worker() -> None:
    compose = _load_compose("docker-compose.gpu.yml")
    services = compose["services"]

    worker_depends_on = services["celery-worker"]["depends_on"]
    api_depends_on = services["api"]["depends_on"]

    assert worker_depends_on["mineru-api"]["condition"] == "service_healthy"
    assert api_depends_on["mineru-api"]["condition"] == "service_healthy"


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
    assert mineru_api["environment"]["MINERU_MODEL_SOURCE"] == "local"
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
    compose = _load_merged_compose("docker-compose.gpu.yml")
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
    assert ("/app/configs", False) in api_volumes
    assert ("/app/data/mineru", False) in api_volumes
    assert ("/root/mineru-runtime", True) in mineru_volumes
    assert worker["environment"]["MINERU_TITLE_AIDED_CONFIG_PATH"] == "/app/data/mineru/mineru-runtime.json"
    assert api["environment"]["MINERU_TITLE_AIDED_CONFIG_PATH"] == "/app/data/mineru/mineru-runtime.json"
    assert (
        mineru_api["environment"]["NEWBEE_MINERU_TITLE_AIDED_CONFIG_JSON"]
        == "/root/mineru-runtime/mineru-runtime.json"
    )
