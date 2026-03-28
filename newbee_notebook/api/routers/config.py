"""Runtime model-switching configuration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from newbee_notebook.api.dependencies import (
    get_db_session,
    reset_embedding_singleton,
    reset_llm_singleton,
)
from newbee_notebook.application.services.app_settings_service import AppSettingsService
from newbee_notebook.core.common.config_db import (
    SYSTEM_DEFAULTS,
    apply_asr_runtime_env,
    apply_embedding_runtime_env,
    apply_llm_runtime_env,
    get_asr_config_async,
    get_embedding_config_async,
    get_llm_config_async,
    resolve_asr_api_key,
)
from newbee_notebook.core.common.project_paths import get_models_directory
from newbee_notebook.core.llm import (
    get_registered_providers as get_registered_llm_providers,
)
from newbee_notebook.core.rag.embeddings import (
    get_registered_providers as get_registered_embedding_providers,
)

router = APIRouter(prefix="/config", tags=["Config"])


class LLMConfigResponse(BaseModel):
    provider: str
    model: str
    temperature: float
    max_tokens: int
    top_p: float
    source: str


class EmbeddingConfigResponse(BaseModel):
    provider: str
    mode: str | None = None
    model: str
    dim: int
    source: str


class ASRConfigResponse(BaseModel):
    provider: str
    model: str
    source: str
    api_key_set: bool


class ModelsConfigResponse(BaseModel):
    llm: LLMConfigResponse
    embedding: EmbeddingConfigResponse
    asr: ASRConfigResponse


class PresetModel(BaseModel):
    name: str
    label: str


class LLMAvailable(BaseModel):
    providers: list[str]
    presets: list[PresetModel]
    custom_input: bool = True


class EmbeddingAvailable(BaseModel):
    providers: list[str]
    modes: list[str]
    api_models: list[PresetModel]
    local_models: list[str]


class ASRAvailable(BaseModel):
    providers: list[str]
    presets: list[PresetModel]


class AvailableModelsResponse(BaseModel):
    llm: LLMAvailable
    embedding: EmbeddingAvailable
    asr: ASRAvailable


class UpdateLLMRequest(BaseModel):
    provider: str
    model: str = Field(min_length=1)
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None


class UpdateEmbeddingRequest(BaseModel):
    provider: str
    mode: str | None = None
    api_model: str | None = None


class UpdateASRRequest(BaseModel):
    provider: str
    model: str | None = None


class ResetResponse(BaseModel):
    message: str
    defaults: dict


def _scan_local_embedding_models() -> list[str]:
    models_dir = get_models_directory()
    if not models_dir.exists():
        return []

    candidates: list[str] = []
    for child in models_dir.iterdir():
        if not child.is_dir():
            continue
        if (child / "config.json").exists() or (child / "model.safetensors").exists():
            candidates.append(child.name)
    return sorted(candidates)


@router.get("/models", response_model=ModelsConfigResponse)
async def get_models_config(session=Depends(get_db_session)):
    llm = await get_llm_config_async(session)
    embedding = await get_embedding_config_async(session)
    asr = await get_asr_config_async(session)
    asr_api_key = resolve_asr_api_key(asr["provider"])
    return ModelsConfigResponse(
        llm=LLMConfigResponse(**llm),
        embedding=EmbeddingConfigResponse(
            provider=embedding["provider"],
            mode=embedding.get("mode"),
            model=embedding["model"],
            dim=embedding["dim"],
            source=embedding["source"],
        ),
        asr=ASRConfigResponse(
            provider=asr["provider"],
            model=asr["model"],
            source=asr["source"],
            api_key_set=bool(asr_api_key),
        ),
    )


@router.get("/models/available", response_model=AvailableModelsResponse)
async def get_available_models():
    return AvailableModelsResponse(
        llm=LLMAvailable(
            providers=[
                provider
                for provider in get_registered_llm_providers()
                if provider in {"qwen", "zhipu", "openai"}
            ],
            presets=[
                PresetModel(name="qwen3.5-plus", label="Qwen 3.5 Plus (Qwen)"),
                PresetModel(name="glm-5", label="GLM-5 (Zhipu)"),
            ],
            custom_input=True,
        ),
        embedding=EmbeddingAvailable(
            providers=[
                provider
                for provider in get_registered_embedding_providers()
                if provider in {"qwen3-embedding", "zhipu"}
            ],
            modes=["local", "api"],
            api_models=[
                PresetModel(name="text-embedding-v4", label="Text Embedding v4 (Qwen)"),
                PresetModel(name="embedding-3", label="Embedding-3 (Zhipu)"),
            ],
            local_models=_scan_local_embedding_models(),
        ),
        asr=ASRAvailable(
            providers=["zhipu", "qwen"],
            presets=[
                PresetModel(name="glm-asr-2512", label="GLM-ASR (Zhipu)"),
                PresetModel(name="qwen3-asr-flash", label="Qwen3-ASR-Flash (Qwen)"),
            ],
        ),
    )


@router.put("/llm", response_model=LLMConfigResponse)
async def update_llm_config(req: UpdateLLMRequest, session=Depends(get_db_session)):
    providers = set(get_registered_llm_providers())
    if req.provider not in providers:
        raise HTTPException(
            status_code=400, detail=f"Unknown LLM provider: {req.provider}"
        )

    if req.temperature is not None and not (0.0 <= req.temperature <= 2.0):
        raise HTTPException(
            status_code=400, detail="temperature must be between 0.0 and 2.0"
        )
    if req.max_tokens is not None and not (1 <= req.max_tokens <= 131072):
        raise HTTPException(
            status_code=400, detail="max_tokens must be between 1 and 131072"
        )
    if req.top_p is not None and not (0.0 <= req.top_p <= 1.0):
        raise HTTPException(status_code=400, detail="top_p must be between 0.0 and 1.0")

    current = await get_llm_config_async(session)
    next_cfg = {
        "provider": req.provider,
        "model": req.model.strip(),
        "temperature": req.temperature
        if req.temperature is not None
        else current["temperature"],
        "max_tokens": req.max_tokens
        if req.max_tokens is not None
        else current["max_tokens"],
        "top_p": req.top_p if req.top_p is not None else current["top_p"],
        "source": "db",
    }

    settings = AppSettingsService(session)
    await settings.set_many(
        {
            "llm.provider": next_cfg["provider"],
            "llm.model": next_cfg["model"],
            "llm.temperature": str(next_cfg["temperature"]),
            "llm.max_tokens": str(next_cfg["max_tokens"]),
            "llm.top_p": str(next_cfg["top_p"]),
        }
    )

    apply_llm_runtime_env(next_cfg)
    reset_llm_singleton()

    return LLMConfigResponse(**next_cfg)


@router.put("/embedding", response_model=EmbeddingConfigResponse)
async def update_embedding_config(
    req: UpdateEmbeddingRequest, session=Depends(get_db_session)
):
    providers = set(get_registered_embedding_providers())
    if req.provider not in providers:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown Embedding provider: {req.provider}",
        )

    current = await get_embedding_config_async(session)

    if req.provider == "qwen3-embedding":
        mode = (req.mode or current.get("mode") or "api").strip().lower()
        if mode not in {"local", "api"}:
            raise HTTPException(status_code=400, detail="mode must be 'local' or 'api'")
        if mode == "local" and not _scan_local_embedding_models():
            raise HTTPException(
                status_code=400,
                detail="No local embedding model found in models/ directory",
            )
        model = req.api_model or current.get("api_model") or "text-embedding-v4"
        next_cfg = {
            "provider": req.provider,
            "mode": mode,
            "model": model
            if mode == "api"
            else current.get("model") or "Qwen3-Embedding-0.6B",
            "api_model": model,
            "dim": int(current.get("dim") or 1024),
            "source": "db",
        }
    else:
        model = req.api_model or current.get("model") or "embedding-3"
        next_cfg = {
            "provider": req.provider,
            "mode": None,
            "model": model,
            "api_model": model,
            "dim": int(current.get("dim") or 1024),
            "source": "db",
        }

    settings = AppSettingsService(session)
    setting_values = {
        "embedding.provider": next_cfg["provider"],
        "embedding.api_model": str(next_cfg["api_model"]),
    }
    if next_cfg.get("mode"):
        setting_values["embedding.mode"] = str(next_cfg["mode"])
    await settings.set_many(setting_values)

    apply_embedding_runtime_env(next_cfg)
    reset_embedding_singleton()

    return EmbeddingConfigResponse(
        provider=next_cfg["provider"],
        mode=next_cfg.get("mode"),
        model=next_cfg["model"],
        dim=next_cfg["dim"],
        source=next_cfg["source"],
    )


@router.put("/asr", response_model=ASRConfigResponse)
async def update_asr_config(req: UpdateASRRequest, session=Depends(get_db_session)):
    provider = str(req.provider or "").strip().lower()
    if provider not in {"zhipu", "qwen"}:
        raise HTTPException(
            status_code=400, detail=f"Unknown ASR provider: {req.provider}"
        )

    api_key = resolve_asr_api_key(provider)
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail=(
                f"API key for provider '{provider}' is not configured. "
                "Please set the corresponding environment variable first."
            ),
        )

    model = str(
        (req.model or ("glm-asr-2512" if provider == "zhipu" else "qwen3-asr-flash"))
    ).strip()
    next_cfg = {
        "provider": provider,
        "model": model,
        "source": "db",
    }

    settings = AppSettingsService(session)
    await settings.set_many(
        {
            "asr.provider": next_cfg["provider"],
            "asr.model": next_cfg["model"],
        }
    )

    apply_asr_runtime_env(next_cfg)

    return ASRConfigResponse(**next_cfg, api_key_set=True)


@router.post("/llm/reset", response_model=ResetResponse)
async def reset_llm_config(session=Depends(get_db_session)):
    settings = AppSettingsService(session)
    await settings.delete_prefix("llm.")

    default_cfg = {**SYSTEM_DEFAULTS["llm"], "source": "default"}
    apply_llm_runtime_env(default_cfg)
    reset_llm_singleton()

    return ResetResponse(
        message="LLM configuration reset to system defaults",
        defaults=SYSTEM_DEFAULTS["llm"],
    )


@router.post("/embedding/reset", response_model=ResetResponse)
async def reset_embedding_config(session=Depends(get_db_session)):
    settings = AppSettingsService(session)
    await settings.delete_prefix("embedding.")

    default_cfg = {**SYSTEM_DEFAULTS["embedding"], "source": "default"}
    apply_embedding_runtime_env(default_cfg)
    reset_embedding_singleton()

    return ResetResponse(
        message="Embedding configuration reset to system defaults",
        defaults=SYSTEM_DEFAULTS["embedding"],
    )


@router.post("/asr/reset", response_model=ResetResponse)
async def reset_asr_config(session=Depends(get_db_session)):
    settings = AppSettingsService(session)
    await settings.delete_prefix("asr.")

    default_cfg = {**SYSTEM_DEFAULTS["asr"], "source": "default"}
    apply_asr_runtime_env(default_cfg)

    return ResetResponse(
        message="ASR configuration reset to system defaults",
        defaults=SYSTEM_DEFAULTS["asr"],
    )
