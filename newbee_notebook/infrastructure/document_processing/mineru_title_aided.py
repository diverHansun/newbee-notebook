"""Prepare MinerU local llm-aided title runtime configuration."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from newbee_notebook.core.common.project_paths import resolve_project_relative_path
from newbee_notebook.core.llm.config import LLMRuntimeConfig, resolve_llm_runtime_config

logger = logging.getLogger(__name__)

RuntimePayload = dict[str, Any]
RuntimeWriter = Callable[[RuntimePayload], None]

_RUNTIME_CONFIG_ENV = "MINERU_TITLE_AIDED_CONFIG_PATH"
_DEFAULT_RUNTIME_CONFIG_PATH = "data/mineru/mineru-runtime.json"


@dataclass(frozen=True)
class MinerUTitleAidedRuntimeResult:
    enabled: bool
    status: str
    reason: str | None
    wrote_file: bool


def get_mineru_title_aided_config_path() -> Path:
    """Return the worker/API side path for the shared MinerU runtime config."""
    configured = os.getenv(_RUNTIME_CONFIG_ENV)
    path_value = configured.strip() if configured else _DEFAULT_RUNTIME_CONFIG_PATH
    return Path(resolve_project_relative_path(path_value))


def _disabled_payload() -> RuntimePayload:
    return {
        "llm-aided-config": {
            "title_aided": {
                "enable": False,
            }
        }
    }


def _enabled_payload(llm_runtime_config: LLMRuntimeConfig | Any) -> RuntimePayload:
    return {
        "llm-aided-config": {
            "title_aided": {
                "enable": True,
                "model": str(llm_runtime_config.model).strip(),
                "api_key": str(llm_runtime_config.api_key),
                "base_url": str(llm_runtime_config.base_url or "").strip(),
            }
        }
    }


def _atomic_write_json(path: Path, payload: RuntimePayload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def write_mineru_title_aided_runtime_config(payload: RuntimePayload) -> None:
    """Atomically write the MinerU runtime config file."""
    _atomic_write_json(get_mineru_title_aided_config_path(), payload)


def _write_payload(writer: RuntimeWriter | None, payload: RuntimePayload) -> None:
    if writer is None:
        write_mineru_title_aided_runtime_config(payload)
        return
    writer(payload)


def _has_llm_api_key(llm_runtime_config: LLMRuntimeConfig | Any | None) -> bool:
    if llm_runtime_config is None:
        return False
    return bool(str(getattr(llm_runtime_config, "api_key", "") or "").strip())


def prepare_mineru_title_aided_runtime(
    mineru_config: dict[str, Any],
    *,
    llm_runtime_config: LLMRuntimeConfig | Any | None,
    writer: RuntimeWriter | None = None,
) -> MinerUTitleAidedRuntimeResult:
    """Prepare local MinerU runtime payload from effective MinerU and chat LLM config."""
    mode = str(mineru_config.get("mode") or "cloud").strip().lower()
    if mode != "local":
        logger.info("MinerU title aided skipped: mode=%s", mode)
        return MinerUTitleAidedRuntimeResult(
            enabled=False,
            status="skipped",
            reason="cloud_mode",
            wrote_file=False,
        )

    if not bool(mineru_config.get("title_aided_enabled", False)):
        _write_payload(writer, _disabled_payload())
        logger.info("MinerU title aided disabled by setting")
        return MinerUTitleAidedRuntimeResult(
            enabled=False,
            status="disabled",
            reason="disabled_by_setting",
            wrote_file=True,
        )

    if not _has_llm_api_key(llm_runtime_config):
        _write_payload(writer, _disabled_payload())
        logger.warning("MinerU title aided disabled: chat LLM API key is not configured")
        return MinerUTitleAidedRuntimeResult(
            enabled=False,
            status="disabled",
            reason="missing_llm_api_key",
            wrote_file=True,
        )

    payload = _enabled_payload(llm_runtime_config)
    _write_payload(writer, payload)
    logger.info(
        "MinerU title aided enabled provider=%s model=%s",
        getattr(llm_runtime_config, "provider", "-"),
        getattr(llm_runtime_config, "model", "-"),
    )
    return MinerUTitleAidedRuntimeResult(
        enabled=True,
        status="enabled",
        reason=None,
        wrote_file=True,
    )


async def prepare_mineru_title_aided_runtime_from_session(
    session: AsyncSession,
    mineru_config: dict[str, Any],
    *,
    writer: RuntimeWriter | None = None,
) -> MinerUTitleAidedRuntimeResult:
    """Resolve chat LLM config only when local title aided is requested."""
    mode = str(mineru_config.get("mode") or "cloud").strip().lower()
    if mode != "local" or not bool(mineru_config.get("title_aided_enabled", False)):
        return prepare_mineru_title_aided_runtime(
            mineru_config,
            llm_runtime_config=None,
            writer=writer,
        )

    try:
        llm_runtime_config = await resolve_llm_runtime_config(session)
    except ValueError:
        logger.warning("MinerU title aided cannot resolve chat LLM runtime config")
        return prepare_mineru_title_aided_runtime(
            mineru_config,
            llm_runtime_config=None,
            writer=writer,
        )

    return prepare_mineru_title_aided_runtime(
        mineru_config,
        llm_runtime_config=llm_runtime_config,
        writer=writer,
    )
