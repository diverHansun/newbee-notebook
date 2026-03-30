"""Database-backed runtime configuration helpers for model switching."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from newbee_notebook.core.common.config import get_embeddings_config, get_llm_config
from newbee_notebook.core.common.project_paths import resolve_project_relative_path

logger = logging.getLogger(__name__)

_TRUTHY = {"1", "true", "yes", "y", "on"}
_FALSY = {"0", "false", "no", "n", "off", ""}
_BILIBILI_CREDENTIAL_KEY = "bilibili.credential"
_BILIBILI_CREDENTIAL_FIELDS = (
    "sessdata",
    "bili_jct",
    "buvid3",
    "buvid4",
    "dedeuserid",
    "ac_time_value",
)


def _get_app_settings_service(session: AsyncSession):
    from newbee_notebook.application.services.app_settings_service import AppSettingsService

    return AppSettingsService(session)


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUTHY:
            return True
        if normalized in _FALSY:
            return False
    return default


def _is_mineru_local_enabled() -> bool:
    raw = os.getenv("MINERU_LOCAL_ENABLED")
    if raw is None:
        # Backward-compatible default for non-docker/local development.
        return True
    return _as_bool(raw, True)


def _normalize_bilibili_credential_payload(payload: Any) -> dict[str, str]:
    if isinstance(payload, dict):
        source = payload
    else:
        source = {
            field: getattr(payload, field, "")
            for field in _BILIBILI_CREDENTIAL_FIELDS
        }
    return {
        field: str(source.get(field, "") or "")
        for field in _BILIBILI_CREDENTIAL_FIELDS
    }


def _read_llm_yaml_defaults() -> dict[str, Any]:
    llm_root = get_llm_config().get("llm", {}) if get_llm_config() else {}
    provider = str(llm_root.get("provider", "qwen") or "qwen").strip().lower()
    provider_cfg = llm_root.get(provider, {}) if isinstance(llm_root, dict) else {}
    return {
        "provider": provider,
        "model": str(provider_cfg.get("model", "qwen3.5-plus")),
        "temperature": _as_float(provider_cfg.get("temperature", 0.7), 0.7),
        "max_tokens": _as_int(provider_cfg.get("max_tokens", 32768), 32768),
        "top_p": _as_float(provider_cfg.get("top_p", 0.8), 0.8),
    }


def _read_embedding_yaml_defaults() -> dict[str, Any]:
    emb_root = get_embeddings_config().get("embeddings", {}) if get_embeddings_config() else {}
    provider = str(emb_root.get("provider", "qwen3-embedding") or "qwen3-embedding").strip().lower()
    provider_cfg = emb_root.get(provider, {}) if isinstance(emb_root, dict) else {}

    if provider == "qwen3-embedding":
        mode = str(provider_cfg.get("mode", "api") or "api").strip().lower()
        api_model = str(provider_cfg.get("api_model", "text-embedding-v4"))
        if mode == "local":
            model_path = str(provider_cfg.get("model_path", "models/Qwen3-Embedding-0.6B"))
            model_name = Path(model_path).name or model_path
        else:
            model_name = api_model
        return {
            "provider": provider,
            "mode": mode,
            "api_model": api_model,
            "model": model_name,
            "dim": _as_int(provider_cfg.get("dim", 1024), 1024),
        }

    return {
        "provider": provider,
        "mode": None,
        "api_model": str(provider_cfg.get("model", "embedding-3")),
        "model": str(provider_cfg.get("model", "embedding-3")),
        "dim": _as_int(provider_cfg.get("dim", 1024), 1024),
    }


_ASR_DEFAULTS: dict[str, Any] = {
    "provider": "zhipu",
    "model": "glm-asr-2512",
}


def _read_mineru_defaults() -> dict[str, Any]:
    mode = str(os.getenv("MINERU_MODE", "cloud") or "cloud").strip().lower()
    if mode not in {"cloud", "local"}:
        mode = "cloud"
    local_enabled = _is_mineru_local_enabled()
    if mode == "local" and not local_enabled:
        mode = "cloud"
    return {
        "mode": mode,
        "local_enabled": local_enabled,
    }


def _default_asr_model_for_provider(provider: str) -> str:
    return {
        "zhipu": "glm-asr-2512",
        "qwen": "qwen3-asr-flash",
    }.get(provider, "glm-asr-2512")


SYSTEM_DEFAULTS: dict[str, Any] = {
    "llm": _read_llm_yaml_defaults(),
    "embedding": _read_embedding_yaml_defaults(),
    "mineru": _read_mineru_defaults(),
    "asr": _ASR_DEFAULTS,
}


def is_model_switch_enabled() -> bool:
    """Feature flag for runtime model switching endpoints/UI."""
    raw = os.getenv("FEATURE_MODEL_SWITCH", "false")
    return raw.strip().lower() in _TRUTHY


async def get_llm_provider_async(session: AsyncSession) -> str:
    cfg = await get_llm_config_async(session)
    return cfg["provider"]


async def get_embedding_provider_async(session: AsyncSession) -> str:
    cfg = await get_embedding_config_async(session)
    return cfg["provider"]


async def get_asr_provider_async(session: AsyncSession) -> str:
    cfg = await get_asr_config_async(session)
    return cfg["provider"]


async def get_mineru_mode_async(session: AsyncSession) -> str:
    cfg = await get_mineru_config_async(session)
    return cfg["mode"]


async def get_bilibili_credential_async(session: AsyncSession) -> dict[str, str] | None:
    raw_value = await _get_app_settings_service(session).get(_BILIBILI_CREDENTIAL_KEY)
    if raw_value is None or not str(raw_value).strip():
        return None

    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        logger.warning("Invalid bilibili credential payload in app_settings")
        return None

    if not isinstance(payload, dict):
        logger.warning("Unexpected bilibili credential payload type in app_settings: %s", type(payload))
        return None

    normalized = _normalize_bilibili_credential_payload(payload)
    if not any(normalized.values()):
        return None
    return normalized


async def save_bilibili_credential_async(session: AsyncSession, payload: Any) -> dict[str, str]:
    normalized = _normalize_bilibili_credential_payload(payload)
    await _get_app_settings_service(session).set(
        _BILIBILI_CREDENTIAL_KEY,
        json.dumps(normalized, ensure_ascii=False),
    )
    return normalized


async def delete_bilibili_credential_async(session: AsyncSession) -> None:
    await _get_app_settings_service(session).delete(_BILIBILI_CREDENTIAL_KEY)


async def get_llm_config_async(session: AsyncSession) -> dict[str, Any]:
    """Get effective LLM config with DB > env > YAML > defaults."""
    defaults = SYSTEM_DEFAULTS["llm"]
    llm_root = get_llm_config().get("llm", {}) if get_llm_config() else {}

    source = "default"
    db_values: dict[str, str] = {}
    try:
        db_values = await _get_app_settings_service(session).get_many("llm.")
        if db_values:
            source = "db"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed reading llm.* from app_settings, fallback chain continues: %s", exc)

    provider = (
        db_values.get("llm.provider")
        or os.getenv("LLM_PROVIDER")
        or llm_root.get("provider")
        or defaults["provider"]
    )
    provider = str(provider).strip().lower() or str(defaults["provider"])

    provider_cfg = llm_root.get(provider, {}) if isinstance(llm_root, dict) else {}

    def _pick(key: str, env_key: str):
        nonlocal source
        db_key = f"llm.{key}"
        if db_key in db_values:
            return db_values[db_key]
        env_val = os.getenv(env_key)
        if env_val is not None and env_val != "":
            if source == "default":
                source = "env"
            return env_val
        if key in provider_cfg:
            if source == "default":
                source = "yaml"
            return provider_cfg[key]
        return defaults[key]

    return {
        "provider": provider,
        "model": str(_pick("model", "LLM_MODEL")),
        "temperature": _as_float(_pick("temperature", "LLM_TEMPERATURE"), float(defaults["temperature"])),
        "max_tokens": _as_int(_pick("max_tokens", "LLM_MAX_TOKENS"), int(defaults["max_tokens"])),
        "top_p": _as_float(_pick("top_p", "LLM_TOP_P"), float(defaults["top_p"])),
        "source": source,
    }


async def get_embedding_config_async(session: AsyncSession) -> dict[str, Any]:
    """Get effective embedding config with DB > env > YAML > defaults."""
    defaults = SYSTEM_DEFAULTS["embedding"]
    emb_root = get_embeddings_config().get("embeddings", {}) if get_embeddings_config() else {}

    source = "default"
    db_values: dict[str, str] = {}
    try:
        db_values = await _get_app_settings_service(session).get_many("embedding.")
        if db_values:
            source = "db"
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed reading embedding.* from app_settings, fallback chain continues: %s",
            exc,
        )

    provider = (
        db_values.get("embedding.provider")
        or os.getenv("EMBEDDING_PROVIDER")
        or emb_root.get("provider")
        or defaults["provider"]
    )
    provider = str(provider).strip().lower() or str(defaults["provider"])

    provider_cfg = emb_root.get(provider, {}) if isinstance(emb_root, dict) else {}

    if provider == "qwen3-embedding":
        mode = (
            db_values.get("embedding.mode")
            or os.getenv("QWEN3_EMBEDDING_MODE")
            or provider_cfg.get("mode")
            or defaults.get("mode")
            or "api"
        )
        mode = str(mode).strip().lower()
        api_model = (
            db_values.get("embedding.api_model")
            or os.getenv("QWEN3_EMBEDDING_API_MODEL")
            or provider_cfg.get("api_model")
            or defaults.get("api_model")
            or "text-embedding-v4"
        )
        if source == "default":
            if any(key in db_values for key in ("embedding.mode", "embedding.api_model", "embedding.model_path")):
                source = "db"
            elif os.getenv("QWEN3_EMBEDDING_MODE") or os.getenv("QWEN3_EMBEDDING_API_MODEL"):
                source = "env"
            elif "mode" in provider_cfg or "api_model" in provider_cfg:
                source = "yaml"

        if mode == "local":
            model_path = (
                db_values.get("embedding.model_path")
                or os.getenv("QWEN3_EMBEDDING_MODEL_PATH")
                or provider_cfg.get("model_path")
                or "models/Qwen3-Embedding-0.6B"
            )
            resolved_model_path = resolve_project_relative_path(str(model_path))
            model_name = Path(str(resolved_model_path)).name or str(resolved_model_path)
        else:
            model_name = str(api_model)
            resolved_model_path = None

        dim = _as_int(
            os.getenv("QWEN3_EMBEDDING_DIM") or provider_cfg.get("dim") or defaults.get("dim", 1024),
            1024,
        )

        return {
            "provider": provider,
            "mode": mode,
            "model": model_name,
            "api_model": str(api_model),
            "model_path": resolved_model_path,
            "dim": dim,
            "source": source,
        }

    model_name = (
        db_values.get("embedding.api_model")
        or os.getenv("EMBEDDING_MODEL")
        or provider_cfg.get("model")
        or defaults.get("model")
        or "embedding-3"
    )
    dim = _as_int(
        os.getenv("EMBEDDING_DIMENSION") or provider_cfg.get("dim") or defaults.get("dim", 1024),
        1024,
    )
    if source == "default":
        if "embedding.api_model" in db_values:
            source = "db"
        elif os.getenv("EMBEDDING_MODEL"):
            source = "env"
        elif "model" in provider_cfg:
            source = "yaml"

    return {
        "provider": provider,
        "mode": None,
        "model": str(model_name),
        "api_model": str(model_name),
        "dim": dim,
        "source": source,
    }


async def get_asr_config_async(session: AsyncSession) -> dict[str, Any]:
    """Get effective ASR config with DB > env > defaults."""
    defaults = SYSTEM_DEFAULTS["asr"]

    source = "default"
    db_values: dict[str, str] = {}
    try:
        db_values = await _get_app_settings_service(session).get_many("asr.")
        if db_values:
            source = "db"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed reading asr.* from app_settings, fallback chain continues: %s", exc)

    provider = (
        db_values.get("asr.provider")
        or os.getenv("ASR_PROVIDER")
        or defaults["provider"]
    )
    provider = str(provider).strip().lower() or str(defaults["provider"])

    model = db_values.get("asr.model")
    if model is None:
        env_model = os.getenv("ASR_MODEL")
        if env_model:
            model = env_model
            if source == "default":
                source = "env"
        else:
            model = _default_asr_model_for_provider(provider)

    if source == "default" and os.getenv("ASR_PROVIDER"):
        source = "env"

    return {
        "provider": provider,
        "model": str(model).strip() or _default_asr_model_for_provider(provider),
        "source": source,
    }


async def get_mineru_config_async(session: AsyncSession) -> dict[str, Any]:
    """Get effective MinerU config with DB > env > defaults + capability guard."""
    defaults = SYSTEM_DEFAULTS["mineru"]
    source = "default"

    db_values: dict[str, str] = {}
    try:
        db_values = await _get_app_settings_service(session).get_many("mineru.")
        if db_values:
            source = "db"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed reading mineru.* from app_settings, fallback chain continues: %s", exc)

    local_enabled = _is_mineru_local_enabled()
    mode = (
        db_values.get("mineru.mode")
        or os.getenv("MINERU_MODE")
        or defaults["mode"]
    )
    mode = str(mode).strip().lower() or str(defaults["mode"])
    if mode not in {"cloud", "local"}:
        mode = str(defaults["mode"])

    if source == "default" and os.getenv("MINERU_MODE"):
        source = "env"

    if mode == "local" and not local_enabled:
        mode = "cloud"

    return {
        "mode": mode,
        "source": source,
        "local_enabled": local_enabled,
    }


def resolve_asr_api_key(provider: str) -> str | None:
    normalized = str(provider or "").strip().lower()
    if normalized == "zhipu":
        return os.getenv("ZHIPU_API_KEY")
    if normalized == "qwen":
        return os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
    return None


def apply_llm_runtime_env(config: dict[str, Any]) -> None:
    """Apply effective LLM config to process env for immediate runtime effect."""
    os.environ["LLM_PROVIDER"] = str(config["provider"])
    os.environ["LLM_MODEL"] = str(config["model"])
    os.environ["LLM_TEMPERATURE"] = str(config["temperature"])
    os.environ["LLM_MAX_TOKENS"] = str(config["max_tokens"])
    os.environ["LLM_TOP_P"] = str(config["top_p"])


def apply_embedding_runtime_env(config: dict[str, Any]) -> None:
    """Apply effective embedding config to process env for immediate runtime effect."""
    provider = str(config["provider"])
    os.environ["EMBEDDING_PROVIDER"] = provider

    if provider == "qwen3-embedding":
        mode = str(config.get("mode") or "api")
        os.environ["QWEN3_EMBEDDING_MODE"] = mode
        if config.get("api_model"):
            os.environ["QWEN3_EMBEDDING_API_MODEL"] = str(config["api_model"])
        if mode == "local":
            model_path = config.get("model_path") or "models/Qwen3-Embedding-0.6B"
            os.environ["QWEN3_EMBEDDING_MODEL_PATH"] = resolve_project_relative_path(str(model_path))
    else:
        os.environ["EMBEDDING_MODEL"] = str(config.get("model") or "embedding-3")


def apply_asr_runtime_env(config: dict[str, Any]) -> None:
    """Apply effective ASR config to process env for immediate runtime effect."""
    os.environ["ASR_PROVIDER"] = str(config["provider"])
    os.environ["ASR_MODEL"] = str(config["model"])


def apply_mineru_runtime_env(config: dict[str, Any]) -> None:
    """Apply effective MinerU config to process env for immediate runtime effect."""
    mode = str(config.get("mode") or "cloud").strip().lower()
    if mode not in {"cloud", "local"}:
        mode = "cloud"
    os.environ["MINERU_MODE"] = mode


async def sync_runtime_env_from_db(session: AsyncSession) -> None:
    """Load effective model config and project into env for runtime builders."""
    llm_cfg = await get_llm_config_async(session)
    emb_cfg = await get_embedding_config_async(session)
    mineru_cfg = await get_mineru_config_async(session)
    asr_cfg = await get_asr_config_async(session)
    apply_llm_runtime_env(llm_cfg)
    apply_embedding_runtime_env(emb_cfg)
    apply_mineru_runtime_env(mineru_cfg)
    apply_asr_runtime_env(asr_cfg)


async def sync_embedding_runtime_env_from_db(session: AsyncSession) -> dict[str, Any]:
    """Load the effective embedding config from DB and project it into process env."""
    emb_cfg = await get_embedding_config_async(session)
    apply_embedding_runtime_env(emb_cfg)
    return emb_cfg


async def sync_mineru_runtime_env_from_db(session: AsyncSession) -> dict[str, Any]:
    """Load the effective MinerU config from DB and project it into process env."""
    mineru_cfg = await get_mineru_config_async(session)
    apply_mineru_runtime_env(mineru_cfg)
    return mineru_cfg
