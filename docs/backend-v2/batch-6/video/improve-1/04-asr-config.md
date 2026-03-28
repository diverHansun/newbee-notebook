# ASR Configuration Design

## Overview

ASR model selection follows the same pattern as LLM and Embedding configuration:
`app_settings` key-value store in DB, config resolution chain (DB > env > YAML > defaults),
API endpoints for read/update/reset, and frontend settings panel integration.

Key constraint: ASR API keys are not stored separately. They reuse the user's existing
LLM provider API keys (Zhipu API key for GLM-ASR, DashScope API key for Qwen ASR).

---

## Database Keys

Stored in `app_settings` table (same as `llm.*` and `embedding.*`):

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `asr.provider` | string | `"zhipu"` | ASR provider: `"zhipu"` or `"qwen"` |
| `asr.model` | string | `"glm-asr-2512"` | Provider-specific model identifier |

Two keys only. No temperature, max_tokens, or other tuning params -- ASR models
have fixed behavior; the only user decision is which provider/model to use.

---

## Provider-Model Mapping

| Provider | Model | API Key Source |
|----------|-------|---------------|
| zhipu | `glm-asr-2512` | `ZHIPU_API_KEY` env var (same as Zhipu LLM) |
| qwen | `qwen3-asr-flash` | `DASHSCOPE_API_KEY` env var (same as Qwen LLM) |

When user selects an ASR provider, the system resolves the API key from the same
environment variable used by that provider's LLM integration. If the key is not
configured, the API endpoint returns a clear error and the frontend shows a prompt
to configure the corresponding LLM provider API key first.

---

## Config Resolution Chain

File: `core/common/config_db.py`

New function following the existing pattern:

```python
_ASR_DEFAULTS: dict[str, Any] = {
    "provider": "zhipu",
    "model": "glm-asr-2512",
}

async def get_asr_config_async(session: AsyncSession) -> dict[str, Any]:
    """Get effective ASR config with DB > env > defaults."""
    source = "default"
    db_values: dict[str, str] = {}
    try:
        db_values = await _get_app_settings_service(session).get_many("asr.")
        if db_values:
            source = "db"
    except Exception:
        pass

    provider = (
        db_values.get("provider")
        or os.getenv("ASR_PROVIDER")
        or _ASR_DEFAULTS["provider"]
    )
    model = (
        db_values.get("model")
        or os.getenv("ASR_MODEL")
        or _default_model_for_provider(provider)
    )

    return {"provider": provider, "model": model, "source": source}


def _default_model_for_provider(provider: str) -> str:
    return {
        "zhipu": "glm-asr-2512",
        "qwen": "qwen3-asr-flash",
    }.get(provider, "glm-asr-2512")
```

Resolution priority: DB (`app_settings.asr.*`) > environment variables (`ASR_PROVIDER`, `ASR_MODEL`) > hardcoded defaults.

No YAML config file for ASR (unlike LLM which has `configs/llm.yaml`). ASR is a simpler
two-field config that doesn't warrant a dedicated YAML file.

---

## API Key Resolution

New helper function:

```python
def resolve_asr_api_key(provider: str) -> str | None:
    """Resolve API key for ASR provider by reusing LLM provider keys."""
    if provider == "zhipu":
        return os.getenv("ZHIPU_API_KEY")
    if provider == "qwen":
        return os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
    return None
```

This function is used by `get_asr_pipeline_dep()` in dependency injection.

---

## Runtime Env Application

```python
def apply_asr_runtime_env(config: dict[str, Any]) -> None:
    os.environ["ASR_PROVIDER"] = str(config["provider"])
    os.environ["ASR_MODEL"] = str(config["model"])
```

Called after PUT/POST reset to ensure in-process env reflects the new config immediately.

---

## API Endpoints

File: `api/routers/config.py`

### Response/Request Models

```python
class ASRConfigResponse(BaseModel):
    provider: str
    model: str
    source: str       # "db" | "env" | "default"
    api_key_set: bool  # whether the provider's API key is configured

class ASRAvailable(BaseModel):
    providers: list[str]           # ["zhipu", "qwen"]
    presets: list[PresetModel]     # [{name: "glm-asr-2512", label: "..."}, ...]

class UpdateASRRequest(BaseModel):
    provider: str
    model: str | None = None  # if None, use default for provider
```

### Endpoints

**GET /config/models** (extend existing)

Add `asr` field to `ModelsConfigResponse`:

```python
class ModelsConfigResponse(BaseModel):
    llm: LLMConfigResponse
    embedding: EmbeddingConfigResponse
    asr: ASRConfigResponse              # new
```

The `api_key_set` field is derived at response time:

```python
asr_cfg = await get_asr_config_async(session)
api_key = resolve_asr_api_key(asr_cfg["provider"])
return ASRConfigResponse(
    **asr_cfg,
    api_key_set=bool(api_key),
)
```

**GET /config/models/available** (extend existing)

Add `asr` field to `AvailableModelsResponse`:

```python
class AvailableModelsResponse(BaseModel):
    llm: LLMAvailable
    embedding: EmbeddingAvailable
    asr: ASRAvailable                   # new
```

Presets:

```python
asr=ASRAvailable(
    providers=["zhipu", "qwen"],
    presets=[
        PresetModel(name="glm-asr-2512", label="GLM-ASR (Zhipu)"),
        PresetModel(name="qwen3-asr-flash", label="Qwen3-ASR-Flash (Qwen)"),
    ],
)
```

**PUT /config/asr**

```python
@router.put("/asr", response_model=ASRConfigResponse)
async def update_asr_config(req: UpdateASRRequest, session=Depends(get_db_session)):
    if req.provider not in {"zhipu", "qwen"}:
        raise HTTPException(status_code=400, detail=f"Unknown ASR provider: {req.provider}")

    api_key = resolve_asr_api_key(req.provider)
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail=f"API key for provider '{req.provider}' is not configured. "
                   f"Please set the corresponding environment variable first.",
        )

    model = (req.model or _default_model_for_provider(req.provider)).strip()
    next_cfg = {"provider": req.provider, "model": model, "source": "db"}

    settings = AppSettingsService(session)
    await settings.set_many({
        "asr.provider": next_cfg["provider"],
        "asr.model": next_cfg["model"],
    })

    apply_asr_runtime_env(next_cfg)
    # No singleton to reset -- ASR pipeline is created per-request

    return ASRConfigResponse(**next_cfg, api_key_set=True)
```

**POST /config/asr/reset**

```python
@router.post("/asr/reset", response_model=ResetResponse)
async def reset_asr_config(session=Depends(get_db_session)):
    settings = AppSettingsService(session)
    await settings.delete_prefix("asr.")

    default_cfg = {**_ASR_DEFAULTS, "source": "default"}
    apply_asr_runtime_env(default_cfg)

    return ResetResponse(
        message="ASR configuration reset to system defaults",
        defaults=_ASR_DEFAULTS,
    )
```

---

## SYSTEM_DEFAULTS Update

```python
SYSTEM_DEFAULTS: dict[str, Any] = {
    "llm": _read_llm_yaml_defaults(),
    "embedding": _read_embedding_yaml_defaults(),
    "asr": _ASR_DEFAULTS,               # new
}
```

---

## Frontend Settings Panel

### Position

In the global settings panel, under "Model" tab, add a third section after LLM and Embedding:

```
Model Tab:
  [LLM Configuration]         -- existing
  [Embedding Configuration]   -- existing
  [ASR Configuration]         -- new
```

### UI Components

**Provider Toggle**: `zhipu` | `qwen` (radio buttons, same style as LLM provider toggle)

**Model Selector**: Dropdown pre-filled with provider presets:
- zhipu selected: show `glm-asr-2512`
- qwen selected: show `qwen3-asr-flash`

**API Key Status Indicator**: Based on `api_key_set` from GET response:
- `true`: green indicator, "API key configured"
- `false`: orange warning, "Please configure {provider} API key in environment variables"

**Reset Button**: "Reset to Default" calls POST /config/asr/reset

### Data Flow

```
Panel mount:
  GET /config/models -> populate all three sections
  GET /config/models/available -> populate dropdowns

User changes ASR provider:
  PUT /config/asr { provider, model }
  <- response includes api_key_set
  Update UI indicators

User clicks reset:
  POST /config/asr/reset
  Refresh section
```

---

## Dependency Injection Integration

The ASR config feeds into the ASR pipeline construction:

```python
# api/dependencies.py

async def get_asr_pipeline_dep(
    bili_client: BilibiliClient = Depends(get_bilibili_client_dep),
    session = Depends(get_db_session),
) -> AsrPipeline | None:
    asr_config = await get_asr_config_async(session)
    provider = asr_config["provider"]
    api_key = resolve_asr_api_key(provider)
    if not api_key:
        return None  # ASR unavailable, VideoService handles gracefully

    if provider == "zhipu":
        transcriber = ZhipuTranscriber(api_key=api_key)
        segment_seconds = 25
    elif provider == "qwen":
        base_url = _resolve_qwen_base_url()
        transcriber = QwenTranscriber(api_key=api_key, base_url=base_url)
        segment_seconds = 270
    else:
        return None

    return AsrPipeline(
        audio_fetcher=_build_audio_fetcher(bili_client),
        segmenter=_build_segmenter(segment_seconds),
        transcriber=transcriber,
    )
```

The `segment_seconds` parameter is derived from the provider config, ensuring
audio is split at the correct granularity for each provider's API limits.

---

## Qwen Base URL Resolution

Qwen ASR endpoint varies by region. Resolution:

```python
def _resolve_qwen_base_url() -> str:
    custom = os.getenv("DASHSCOPE_BASE_URL")
    if custom:
        return custom
    return "https://dashscope.aliyuncs.com/api/v1"
```

This allows users in international regions to override with:
- Singapore: `https://dashscope-intl.aliyuncs.com/api/v1`
- US: `https://dashscope-us.aliyuncs.com/api/v1`

---

## Migration

No database migration needed. The `app_settings` table is a key-value store --
new `asr.*` keys are written on first PUT request. Default values are hardcoded
in the resolution chain, so the system works out of the box without any DB entries.
