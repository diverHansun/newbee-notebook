# 后端 API 设计: 模型配置读写与单例管理

本文档定义后端侧的完整实现方案，包括数据库模型、API 端点、配置优先级链改造、单例重置机制和 Celery Worker 同步策略。

---

## 1. 数据库模型

### 1.1 `app_settings` 表

新增 `app_settings` 表用于持久化用户自定义配置。表结构极简，采用 Key-Value 设计以适配任意配置项。

```sql
CREATE TABLE IF NOT EXISTS app_settings (
    key         VARCHAR(128)    PRIMARY KEY,
    value       TEXT            NOT NULL,
    updated_at  TIMESTAMP       NOT NULL DEFAULT NOW()
);
```

### 1.2 ORM 模型

在 `infrastructure/persistence/models.py` 中新增:

```python
class AppSettingModel(Base):
    """Application settings table - key-value store for user config overrides."""
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
```

### 1.3 Schema 迁移

遵循现有 `database.py` 的 `_ensure_runtime_schema()` 模式，在启动时自动建表:

```python
await conn.execute(
    text(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            key         VARCHAR(128)    PRIMARY KEY,
            value       TEXT            NOT NULL,
            updated_at  TIMESTAMP       NOT NULL DEFAULT NOW()
        )
        """
    )
)
```

无需 Alembic 迁移脚本，与现有项目的 schema 管理方式保持一致。

### 1.4 预定义的 Key 名称

| Key | 类型 | 示例值 | 说明 |
|-----|------|--------|------|
| `llm.provider` | string | `"qwen"` | LLM provider 选择 |
| `llm.model` | string | `"qwen3.5-plus"` | 模型名称 (支持自由输入) |
| `llm.temperature` | float | `"0.7"` | 采样温度 |
| `llm.max_tokens` | int | `"32768"` | 最大输出 token 数 |
| `llm.top_p` | float | `"0.8"` | Top-p 采样 |
| `embedding.provider` | string | `"qwen3-embedding"` | Embedding provider |
| `embedding.mode` | string | `"api"` | qwen3-embedding 的模式 |
| `embedding.api_model` | string | `"text-embedding-v4"` | API 模式的模型名 |

所有 value 均以字符串存储，读取时由应用层转换类型。Key 名称使用点号分隔的命名空间约定。

---

## 2. 配置读取服务

### 2.1 新增 `AppSettingsService`

在 `application/services/` 下新增 `app_settings_service.py`，封装 DB 读写逻辑:

```python
class AppSettingsService:
    """Application settings CRUD service."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, key: str) -> Optional[str]:
        """Get a setting value by key. Returns None if not set."""
        result = await self._session.execute(
            select(AppSettingModel).where(AppSettingModel.key == key)
        )
        row = result.scalar_one_or_none()
        return row.value if row else None

    async def get_many(self, prefix: str) -> Dict[str, str]:
        """Get all settings matching a key prefix (e.g. 'llm.')."""
        result = await self._session.execute(
            select(AppSettingModel).where(AppSettingModel.key.like(f"{prefix}%"))
        )
        return {row.key: row.value for row in result.scalars()}

    async def set(self, key: str, value: str) -> None:
        """Upsert a setting. Uses INSERT ON CONFLICT UPDATE."""
        stmt = pg_insert(AppSettingModel).values(
            key=key, value=value, updated_at=datetime.now()
        ).on_conflict_do_update(
            index_elements=["key"],
            set_={"value": value, "updated_at": datetime.now()},
        )
        await self._session.execute(stmt)

    async def set_many(self, settings: Dict[str, str]) -> None:
        """Batch upsert multiple settings."""
        for key, value in settings.items():
            await self.set(key, value)

    async def delete(self, key: str) -> None:
        """Delete a setting (revert to system default)."""
        await self._session.execute(
            delete(AppSettingModel).where(AppSettingModel.key == key)
        )

    async def delete_prefix(self, prefix: str) -> None:
        """Delete all settings matching a prefix (restore defaults for a section)."""
        await self._session.execute(
            delete(AppSettingModel).where(AppSettingModel.key.like(f"{prefix}%"))
        )
```

### 2.2 配置优先级链改造

改造 `config.py` 中的 getter 函数，在最顶层插入 DB 查询。以 `get_llm_provider()` 为例:

```
改造前:  env > YAML > 硬编码默认
改造后:  DB > env > YAML > 硬编码默认
```

由于 `config.py` 中的函数为同步函数，而 DB 查询为异步操作，采用以下策略:

- 新增 `config_db.py` 模块，提供异步配置读取函数
- 每个需要 DB 支持的 getter 增加一个 `async` 版本
- 在 API 层 (路由和依赖注入) 使用异步版本
- Celery Worker 同步读取 DB (通过 `asyncio.run()` 或同步 session)

```python
# core/common/config_db.py

async def get_llm_provider_async(session: AsyncSession) -> str:
    """Get LLM provider with DB-first priority."""
    # 1. DB
    result = await session.execute(
        select(AppSettingModel).where(AppSettingModel.key == "llm.provider")
    )
    row = result.scalar_one_or_none()
    if row:
        return row.value

    # 2. 环境变量
    provider = os.getenv("LLM_PROVIDER")
    if provider and provider.strip():
        return provider.strip().lower()

    # 3. YAML
    llm_config = get_llm_config()
    if llm_config and "llm" in llm_config:
        provider = llm_config["llm"].get("provider")
        if provider:
            return str(provider).strip().lower()

    # 4. 硬编码默认
    return "qwen"
```

### 2.3 系统默认值常量

在 `config_db.py` 中定义系统默认值，供"恢复默认"功能使用:

```python
SYSTEM_DEFAULTS = {
    "llm": {
        "provider": "qwen",
        "model": "qwen3.5-plus",
        "temperature": 0.7,
        "max_tokens": 32768,
        "top_p": 0.8,
    },
    "embedding": {
        "provider": "qwen3-embedding",
        "mode": "api",
        "api_model": "text-embedding-v4",
    },
}
```

---

## 3. API 端点设计

### 3.1 路由注册

在 `api/routers/` 下新增 `config.py`，路由前缀为 `/config`:

```python
# api/routers/config.py
router = APIRouter(prefix="/config", tags=["Config"])
```

在 `main.py` 中注册:

```python
from newbee_notebook.api.routers import config
app.include_router(config.router, prefix="/api/v1", tags=["Config"])
```

最终路径: `GET/PUT /api/v1/config/...`

### 3.2 端点列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/config/models` | 获取当前生效的 LLM + Embedding 配置 |
| GET | `/config/models/available` | 获取可用的 providers、预设模型列表 |
| PUT | `/config/llm` | 更新 LLM 配置 |
| PUT | `/config/embedding` | 更新 Embedding 配置 |
| POST | `/config/llm/reset` | 恢复 LLM 默认配置 |
| POST | `/config/embedding/reset` | 恢复 Embedding 默认配置 |

### 3.3 请求/响应模型

```python
# === 响应模型 ===

class LLMConfigResponse(BaseModel):
    provider: str                         # "qwen" | "zhipu"
    model: str                            # 当前模型名
    temperature: float
    max_tokens: int
    top_p: float
    source: str                           # "db" | "env" | "yaml" | "default"

class EmbeddingConfigResponse(BaseModel):
    provider: str                         # "qwen3-embedding" | "zhipu"
    mode: Optional[str]                   # "local" | "api" (仅 qwen3-embedding)
    model: str                            # 当前使用的模型名
    dim: int                              # 向量维度 (只读，固定 1024)
    source: str

class ModelsConfigResponse(BaseModel):
    llm: LLMConfigResponse
    embedding: EmbeddingConfigResponse

# === 可用选项 ===

class PresetModel(BaseModel):
    name: str                             # 模型名称
    label: str                            # 显示标签（含 provider 信息）

class LLMAvailable(BaseModel):
    providers: list[str]                  # ["qwen", "zhipu"]
    presets: list[PresetModel]            # 预设模型
    custom_input: bool                    # True - 支持自由输入模型名

class EmbeddingAvailable(BaseModel):
    providers: list[str]                  # ["qwen3-embedding", "zhipu"]
    modes: list[str]                      # ["local", "api"]
    api_models: list[PresetModel]         # API 模式可选模型
    local_models: list[str]              # 本地 models/ 目录下的模型

class AvailableModelsResponse(BaseModel):
    llm: LLMAvailable
    embedding: EmbeddingAvailable

# === 请求模型 ===

class UpdateLLMRequest(BaseModel):
    provider: str                         # "qwen" | "zhipu"
    model: str                            # 模型名称 (支持自由输入)
    temperature: Optional[float] = None   # 0.0-2.0
    max_tokens: Optional[int] = None      # 1-131072
    top_p: Optional[float] = None         # 0.0-1.0

class UpdateEmbeddingRequest(BaseModel):
    provider: str                         # "qwen3-embedding" | "zhipu"
    mode: Optional[str] = None            # "local" | "api" (仅 qwen3-embedding)
    api_model: Optional[str] = None       # API 模式的模型名

class ResetResponse(BaseModel):
    message: str
    defaults: dict                        # 恢复后的默认值
```

### 3.4 端点实现逻辑

#### GET `/config/models` - 获取当前配置

```python
@router.get("/models", response_model=ModelsConfigResponse)
async def get_models_config(session=Depends(get_db_session)):
    settings = AppSettingsService(session)

    # 逐级 fallback 读取 LLM 配置
    llm_provider = await settings.get("llm.provider") or get_llm_provider()
    llm_model = await settings.get("llm.model") or _get_yaml_llm_model(llm_provider)
    # ... 类推 temperature, max_tokens, top_p
    llm_source = "db" if await settings.get("llm.provider") else _detect_source("llm")

    # Embedding 配置
    emb_provider = await settings.get("embedding.provider") or get_embedding_provider()
    # ...

    return ModelsConfigResponse(llm=..., embedding=...)
```

#### PUT `/config/llm` - 更新 LLM 配置

```python
@router.put("/llm", response_model=LLMConfigResponse)
async def update_llm_config(
    req: UpdateLLMRequest,
    session=Depends(get_db_session),
):
    # 1. 校验 provider 是否已注册
    if req.provider not in get_registered_llm_providers():
        raise HTTPException(400, f"Unknown LLM provider: {req.provider}")

    # 2. 校验参数范围
    if req.temperature is not None and not (0.0 <= req.temperature <= 2.0):
        raise HTTPException(400, "temperature must be between 0.0 and 2.0")
    if req.top_p is not None and not (0.0 <= req.top_p <= 1.0):
        raise HTTPException(400, "top_p must be between 0.0 and 1.0")

    # 3. 写入 DB
    settings = AppSettingsService(session)
    await settings.set("llm.provider", req.provider)
    await settings.set("llm.model", req.model)
    if req.temperature is not None:
        await settings.set("llm.temperature", str(req.temperature))
    if req.max_tokens is not None:
        await settings.set("llm.max_tokens", str(req.max_tokens))
    if req.top_p is not None:
        await settings.set("llm.top_p", str(req.top_p))

    # 4. 重置 LLM 单例
    reset_llm_singleton()

    # 5. 返回更新后的配置
    return LLMConfigResponse(
        provider=req.provider,
        model=req.model,
        temperature=req.temperature or SYSTEM_DEFAULTS["llm"]["temperature"],
        max_tokens=req.max_tokens or SYSTEM_DEFAULTS["llm"]["max_tokens"],
        top_p=req.top_p or SYSTEM_DEFAULTS["llm"]["top_p"],
        source="db",
    )
```

#### PUT `/config/embedding` - 更新 Embedding 配置

```python
@router.put("/embedding", response_model=EmbeddingConfigResponse)
async def update_embedding_config(
    req: UpdateEmbeddingRequest,
    session=Depends(get_db_session),
):
    # 1. 校验 provider
    if req.provider not in get_registered_embedding_providers():
        raise HTTPException(400, f"Unknown Embedding provider: {req.provider}")

    # 2. 校验 mode (仅 qwen3-embedding 支持 local/api 切换)
    if req.provider == "qwen3-embedding" and req.mode:
        if req.mode not in ("local", "api"):
            raise HTTPException(400, "mode must be 'local' or 'api'")

    # 3. 写入 DB
    settings = AppSettingsService(session)
    await settings.set("embedding.provider", req.provider)
    if req.mode:
        await settings.set("embedding.mode", req.mode)
    if req.api_model:
        await settings.set("embedding.api_model", req.api_model)

    # 4. 重置 Embedding 和 pgvector Index 单例
    reset_embedding_singleton()

    return EmbeddingConfigResponse(...)
```

#### POST `/config/llm/reset` - 恢复 LLM 默认

```python
@router.post("/llm/reset", response_model=ResetResponse)
async def reset_llm_config(session=Depends(get_db_session)):
    settings = AppSettingsService(session)
    await settings.delete_prefix("llm.")
    reset_llm_singleton()
    return ResetResponse(
        message="LLM configuration reset to system defaults",
        defaults=SYSTEM_DEFAULTS["llm"],
    )
```

#### POST `/config/embedding/reset` - 恢复 Embedding 默认

```python
@router.post("/embedding/reset", response_model=ResetResponse)
async def reset_embedding_config(session=Depends(get_db_session)):
    settings = AppSettingsService(session)
    await settings.delete_prefix("embedding.")
    reset_embedding_singleton()
    return ResetResponse(
        message="Embedding configuration reset to system defaults",
        defaults=SYSTEM_DEFAULTS["embedding"],
    )
```

#### GET `/config/models/available` - 可用选项

```python
@router.get("/models/available", response_model=AvailableModelsResponse)
async def get_available_models():
    # LLM 预设
    llm_presets = [
        PresetModel(name="qwen3.5-plus", label="Qwen 3.5 Plus (Qwen)"),
        PresetModel(name="glm-4.7-flash", label="GLM-4.7-Flash (Zhipu)"),
    ]

    # 扫描本地模型目录
    local_models = _scan_local_embedding_models()

    # API Embedding 预设
    api_models = [
        PresetModel(name="text-embedding-v4", label="Text Embedding v4 (Qwen)"),
        PresetModel(name="embedding-3", label="Embedding-3 (Zhipu)"),
    ]

    return AvailableModelsResponse(
        llm=LLMAvailable(
            providers=["qwen", "zhipu"],
            presets=llm_presets,
            custom_input=True,
        ),
        embedding=EmbeddingAvailable(
            providers=["qwen3-embedding", "zhipu"],
            modes=["local", "api"],
            api_models=api_models,
            local_models=local_models,
        ),
    )
```

本地模型扫描逻辑:

```python
def _scan_local_embedding_models() -> list[str]:
    """Scan models/ directory for valid local embedding models."""
    models_dir = Path("models")
    if not models_dir.exists():
        return []
    result = []
    for child in models_dir.iterdir():
        if child.is_dir() and (
            (child / "config.json").exists()
            or (child / "model.safetensors").exists()
        ):
            result.append(child.name)
    return result
```

---

## 4. 单例重置机制

### 4.1 改造 `dependencies.py`

在现有单例管理代码旁新增重置函数:

```python
def reset_llm_singleton() -> None:
    """Reset the LLM singleton. Next call to get_llm_singleton() will rebuild."""
    global _llm
    _llm = None
    logger.info("LLM singleton reset")


def reset_embedding_singleton() -> None:
    """Reset Embedding and pgvector Index singletons.
    
    pgvector index depends on embedding provider for table routing,
    so both must be reset together.
    """
    global _embed_model, _pgvector_index
    _embed_model = None
    _pgvector_index = None
    logger.info("Embedding and pgvector index singletons reset")
```

### 4.2 重置触发时机

| 操作 | 重置目标 | 原因 |
|------|----------|------|
| PUT `/config/llm` | `_llm` | LLM provider/model/参数变更 |
| PUT `/config/embedding` | `_embed_model` + `_pgvector_index` | Embedding 变更影响向量表路由 |
| POST `/config/llm/reset` | `_llm` | 恢复默认后需重建 |
| POST `/config/embedding/reset` | `_embed_model` + `_pgvector_index` | 同上 |

### 4.3 SessionManager 的特殊处理

当前 `get_session_manager_singleton()` 已经每次请求创建新的 LLM 实例 (`llm = build_llm()`)。但它依赖 `get_pg_index_singleton()` 获取 pgvector index，因此:

- LLM 切换: SessionManager 自然感知 (每次重建)
- Embedding 切换: pgvector index 被重置后，SessionManager 下次请求会获取新 index

这意味着 **SessionManager 无需额外修改**。

### 4.4 线程安全

FastAPI 使用 asyncio 事件循环，单线程执行，因此全局变量的 `None` 赋值是原子操作，无需加锁。

如果未来引入多 Worker (如 Gunicorn + Uvicorn)，每个 Worker 是独立进程，各自拥有独立的全局变量，通过各自读取 DB 获得最新配置。

---

## 5. Celery Worker 同步策略

### 5.1 问题

Celery Worker 是独立进程，拥有自己的 `_EMBED_MODEL` 全局单例。API 进程中的 `reset_embedding_singleton()` 无法影响 Worker 进程。

### 5.2 方案: 按任务读取最新配置

改造 Worker 中的 `_get_embed_model()`:

```python
# infrastructure/tasks/document_tasks.py

_EMBED_MODEL = None
_EMBED_PROVIDER_KEY = None  # 记录当前缓存对应的 provider

def _get_embed_model():
    global _EMBED_MODEL, _EMBED_PROVIDER_KEY

    # 每次任务执行时检查 DB 中的最新 provider
    current_provider = _get_db_embedding_provider()  # 同步读取 DB

    if _EMBED_MODEL is None or current_provider != _EMBED_PROVIDER_KEY:
        # 首次初始化 或 provider 已变更
        _EMBED_MODEL = build_embedding()
        _EMBED_PROVIDER_KEY = current_provider
        logger.info(f"Celery Worker: Embedding model rebuilt for provider={current_provider}")

    return _EMBED_MODEL
```

同步读取 DB 的辅助函数:

```python
def _get_db_embedding_provider() -> Optional[str]:
    """Synchronously read embedding.provider from app_settings."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as SyncSession

    engine = create_engine(get_sync_database_url())
    with SyncSession(engine) as session:
        row = session.execute(
            select(AppSettingModel).where(AppSettingModel.key == "embedding.provider")
        ).scalar_one_or_none()
        return row.value if row else None
```

### 5.3 性能考量

- 每个文档索引任务执行一次 DB 查询 (SELECT 单行)，开销极低
- 只有 provider 变更时才重建模型，本地模型加载 (SentenceTransformer) 约 2-3 秒
- 可选优化: 添加 TTL 缓存 (如 30 秒)，减少 DB 查询频率

---

## 6. 校验规则

### 6.1 LLM 参数校验

| 参数 | 类型 | 范围 | 默认值 |
|------|------|------|--------|
| provider | string | `qwen`, `zhipu` (已注册的 provider) | `qwen` |
| model | string | 任意非空字符串 | `qwen3.5-plus` |
| temperature | float | 0.0 - 2.0 | 0.7 |
| max_tokens | int | 1 - 131072 | 32768 |
| top_p | float | 0.0 - 1.0 | 0.8 |

### 6.2 Embedding 参数校验

| 参数 | 类型 | 范围 | 默认值 |
|------|------|------|--------|
| provider | string | `qwen3-embedding`, `zhipu` | `qwen3-embedding` |
| mode | string | `local`, `api` (仅 qwen3-embedding) | `api` |
| api_model | string | `text-embedding-v4`, `embedding-3` | `text-embedding-v4` |

### 6.3 跨参数约束

1. `provider=zhipu` 时，`mode` 字段无效 (zhipu 仅支持 API 模式)
2. `provider=qwen3-embedding` + `mode=local` 时，需检查 `models/` 下是否有可用模型
3. LLM `model` 字段为自由输入，容错处理: 如果 API 调用报错 (模型不存在)，由后续使用时暴露

---

## 7. 错误处理

### 7.1 HTTP 状态码

| 场景 | 状态码 | 消息 |
|------|--------|------|
| 未知 provider | 400 | `Unknown LLM/Embedding provider: {name}` |
| 参数范围越界 | 400 | `{param} must be between {min} and {max}` |
| 本地模型不存在 | 400 | `No local embedding model found in models/ directory` |
| DB 读取失败 | 500 | `Failed to read configuration from database` |

### 7.2 容错策略

- DB 查询失败时，降级到 env > YAML > 默认值链，不阻塞请求
- 单例重置后首次重建失败时，返回 500 且保持 `_llm = None`，下次请求重试
- API Key 缺失由 Builder 函数抛出，不在 config 层拦截

---

## 8. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `infrastructure/persistence/models.py` | 修改 | 新增 `AppSettingModel` |
| `infrastructure/persistence/database.py` | 修改 | `_ensure_runtime_schema()` 追加建表语句 |
| `application/services/app_settings_service.py` | 新增 | 配置 CRUD 服务 |
| `core/common/config_db.py` | 新增 | 异步配置读取函数、系统默认值常量 |
| `api/routers/config.py` | 新增 | 配置管理路由 (6 个端点) |
| `api/routers/__init__.py` | 修改 | 导出 config 模块 |
| `api/main.py` | 修改 | 注册 config 路由 |
| `api/dependencies.py` | 修改 | 新增 `reset_llm_singleton()`, `reset_embedding_singleton()` |
| `infrastructure/tasks/document_tasks.py` | 修改 | Worker 按任务读取 DB 配置 |
