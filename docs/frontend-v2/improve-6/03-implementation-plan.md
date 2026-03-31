# 实施方案 - API Key 状态指示器统一补全

## 改动范围概览

| 文件 | 改动类型 |
|---|---|
| `newbee_notebook/core/common/config_db.py` | 新增 3 个 resolve 函数；更新 `resolve_asr_api_key` 的导出 |
| `newbee_notebook/api/routers/config.py` | Response 类新增字段；`get_models_config()` 补充逻辑；补充 import |
| `frontend/src/lib/api/config.ts` | 3 个接口新增 `api_key_set` 字段 |
| `frontend/src/components/layout/model-config-panel.tsx` | Draft 类型、转换函数、UI 渲染三处修改 |
| `frontend/src/lib/i18n/strings.ts` | 新增 3 条共用 i18n 字符串 |

---

## 步骤一：后端 config_db.py

**文件**：`newbee_notebook/core/common/config_db.py`

在 `resolve_asr_api_key`（第 460-466 行）之后新增以下三个函数：

```python
def resolve_llm_api_key(provider: str) -> str | None:
    normalized = str(provider or "").strip().lower()
    if normalized == "zhipu":
        return os.getenv("ZHIPU_API_KEY")
    if normalized == "qwen":
        return os.getenv("DASHSCOPE_API_KEY")
    return None


_NOT_APPLICABLE = "__not_applicable__"


def resolve_embedding_api_key(provider: str, mode: str | None) -> str | None:
    """
    返回 _NOT_APPLICABLE 表示当前配置不依赖 API key（qwen3-embedding local 模式）。
    返回 None 或空字符串表示需要但未配置。
    """
    normalized_provider = str(provider or "").strip().lower()
    if normalized_provider == "qwen3-embedding":
        if str(mode or "").strip().lower() == "local":
            return _NOT_APPLICABLE
        return os.getenv("DASHSCOPE_API_KEY")
    if normalized_provider == "zhipu":
        return os.getenv("ZHIPU_API_KEY")
    return None


def resolve_mineru_api_key(mode: str) -> str | None:
    """
    返回 _NOT_APPLICABLE 表示 local 模式不依赖 API key。
    """
    if str(mode or "").strip().lower() == "local":
        return _NOT_APPLICABLE
    return os.getenv("MINERU_API_KEY")
```

---

## 步骤二：后端 config.py

**文件**：`newbee_notebook/api/routers/config.py`

### 2.1 更新 import

在现有 import 行（第 24 行）中，将 `resolve_asr_api_key` 替换为：

```python
from newbee_notebook.core.common.config_db import (
    ...
    resolve_asr_api_key,
    resolve_embedding_api_key,
    resolve_llm_api_key,
    resolve_mineru_api_key,
)
```

同时在文件顶部从 `config_db` 导入 `_NOT_APPLICABLE`，或在 `config.py` 内部直接使用字符串常量
`"__not_applicable__"` 与之对应。推荐将 `_NOT_APPLICABLE` 从 `config_db` 导出，
在 `config.py` 引用。

### 2.2 修改 Response 类

**LLMConfigResponse**（第 37-43 行）新增一行：

```python
class LLMConfigResponse(BaseModel):
    provider: str
    model: str
    temperature: float
    max_tokens: int
    top_p: float
    source: str
    api_key_set: bool          # 新增
```

**EmbeddingConfigResponse**（第 46-51 行）新增一行：

```python
class EmbeddingConfigResponse(BaseModel):
    provider: str
    mode: str | None = None
    model: str
    dim: int
    source: str
    api_key_set: bool | None = None    # 新增；None 表示当前模式不需要 key
```

**MinerUConfigResponse**（第 61-64 行）新增一行：

```python
class MinerUConfigResponse(BaseModel):
    mode: str
    source: str
    local_enabled: bool
    api_key_set: bool | None = None    # 新增；None 表示 local 模式不需要 key
```

### 2.3 修改 get_models_config()

**文件**：`config.py` 第 150-177 行

在原有逻辑基础上，补充三个 key 检查调用：

```python
@router.get("/models", response_model=ModelsConfigResponse)
async def get_models_config(session=Depends(get_db_session)):
    llm = await get_llm_config_async(session)
    embedding = await get_embedding_config_async(session)
    mineru = await get_mineru_config_async(session)
    asr = await get_asr_config_async(session)

    asr_api_key = resolve_asr_api_key(asr["provider"])

    # 新增：LLM key 检查
    llm_api_key = resolve_llm_api_key(llm["provider"])

    # 新增：Embedding key 检查（需传入 mode）
    emb_raw = resolve_embedding_api_key(embedding["provider"], embedding.get("mode"))
    emb_api_key_set = None if emb_raw == _NOT_APPLICABLE else bool(emb_raw)

    # 新增：MinerU key 检查（需传入 mode）
    mineru_raw = resolve_mineru_api_key(mineru["mode"])
    mineru_api_key_set = None if mineru_raw == _NOT_APPLICABLE else bool(mineru_raw)

    return ModelsConfigResponse(
        llm=LLMConfigResponse(**llm, api_key_set=bool(llm_api_key)),   # 新增 api_key_set
        embedding=EmbeddingConfigResponse(
            provider=embedding["provider"],
            mode=embedding.get("mode"),
            model=embedding["model"],
            dim=embedding["dim"],
            source=embedding["source"],
            api_key_set=emb_api_key_set,    # 新增
        ),
        mineru=MinerUConfigResponse(
            mode=mineru["mode"],
            source=mineru["source"],
            local_enabled=bool(mineru.get("local_enabled", False)),
            api_key_set=mineru_api_key_set,  # 新增
        ),
        asr=ASRConfigResponse(
            provider=asr["provider"],
            model=asr["model"],
            source=asr["source"],
            api_key_set=bool(asr_api_key),
        ),
    )
```

注意：`LLMConfigResponse(**llm, api_key_set=...)` 仅在 `llm` dict 中不含 `api_key_set`
键时才能直接用 `**llm`。若 `get_llm_config_async` 返回的 dict 键与 Response 字段完全对应，
改为显式传参，与 Embedding 和 MinerU 保持一致。

---

## 步骤三：前端 config.ts

**文件**：`frontend/src/lib/api/config.ts`

### LLMConfig（第 3-10 行）

```typescript
export interface LLMConfig {
  provider: string;
  model: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
  source: string;
  api_key_set: boolean;    // 新增
}
```

### EmbeddingConfig（第 12-18 行）

```typescript
export interface EmbeddingConfig {
  provider: string;
  mode: string | null;
  model: string;
  dim: number;
  source: string;
  api_key_set: boolean | null;    // 新增
}
```

### MinerUConfig（第 27-31 行）

```typescript
export interface MinerUConfig {
  mode: string;
  source: string;
  local_enabled: boolean;
  api_key_set: boolean | null;    // 新增
}
```

---

## 步骤四：前端 model-config-panel.tsx

**文件**：`frontend/src/components/layout/model-config-panel.tsx`

### 4.1 Draft 类型更新

**LLMDraft**（第 27-33 行）新增：

```typescript
type LLMDraft = {
  provider: string;
  model: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
  api_key_set: boolean;    // 新增
};
```

**EmbeddingDraft**（第 35-41 行）新增：

```typescript
type EmbeddingDraft = {
  provider: string;
  mode: string | null;
  api_model: string;
  model: string;
  dim: number;
  api_key_set: boolean | null;    // 新增
};
```

**MinerUDraft**（第 49-53 行）新增：

```typescript
type MinerUDraft = {
  mode: string;
  source: string;
  local_enabled: boolean;
  api_key_set: boolean | null;    // 新增
};
```

### 4.2 转换函数更新

**toLLMDraft**（第 78-86 行）新增一行：

```typescript
function toLLMDraft(config: LLMConfig): LLMDraft {
  return {
    provider: config.provider,
    model: config.model,
    temperature: config.temperature,
    max_tokens: config.max_tokens,
    top_p: config.top_p,
    api_key_set: config.api_key_set,    // 新增
  };
}
```

**toEmbeddingDraft**（第 88-96 行）新增一行：

```typescript
function toEmbeddingDraft(config: EmbeddingConfig): EmbeddingDraft {
  return {
    provider: config.provider,
    mode: config.mode,
    api_model: config.model,
    model: config.model,
    dim: config.dim,
    api_key_set: config.api_key_set,    // 新增
  };
}
```

**toMinerUDraft**（第 106-112 行）新增一行：

```typescript
function toMinerUDraft(config: MinerUConfig): MinerUDraft {
  return {
    mode: config.mode,
    source: config.source,
    local_enabled: config.local_enabled,
    api_key_set: config.api_key_set,    // 新增
  };
}
```

### 4.3 UI 渲染

在 LLM、Embedding、MinerU 各自的配置卡片中，于最后一个可编辑字段之后追加状态行。

三处结构相同：

```tsx
{llmDraft.api_key_set !== null && (
  <div className="control-panel-readonly-row">
    <span className="control-panel-readonly-label">
      {t(uiStrings.controlPanel.apiKeyStatus)}
    </span>
    <span className="control-panel-status">
      <span
        className={`control-panel-status-dot${llmDraft.api_key_set ? " is-ok" : ""}`}
        aria-hidden="true"
      />
      <span>
        {llmDraft.api_key_set
          ? t(uiStrings.controlPanel.apiKeyConfigured)
          : t(uiStrings.controlPanel.apiKeyMissing)}
      </span>
    </span>
  </div>
)}
```

LLM 的 `api_key_set` 类型为 `boolean`（非 nullable），条件判断可省略 `!== null` 检查，
但保留更安全，便于后续扩展。

Embedding 和 MinerU 中将 `llmDraft` 替换为对应的 draft 变量名。

---

## 步骤五：前端 i18n strings.ts

**文件**：`frontend/src/lib/i18n/strings.ts`

在 `controlPanel` 对象中，紧跟 `asrApiKeyMissing` 字段（约第 206-209 行）之后新增：

```typescript
apiKeyStatus:     { zh: "API Key",  en: "API key" },
apiKeyConfigured: { zh: "已配置",   en: "Configured" },
apiKeyMissing:    { zh: "未配置",   en: "Not configured" },
```

这三条字符串供 LLM、Embedding、MinerU 共用。ASR 继续沿用自己的
`asrApiKeyStatus` / `asrApiKeyConfigured` / `asrApiKeyMissing`，不修改。

---

## 步骤六：验证要点

1. `GET /api/v1/config/models` 响应中，LLM、Embedding（api 模式）、MinerU（cloud 模式）
   的 `api_key_set` 均为 `true` 或 `false`，Embedding（local 模式）和 MinerU（local 模式）
   的 `api_key_set` 为 `null`。

2. 控制面板中，三个配置卡片在需要 key 的模式下显示状态行；
   Embedding 切换到 local 模式后状态行消失；MinerU 切换到 local 模式后状态行消失。

3. 所有已有 ASR 相关的指示器逻辑不受影响。

4. `model-config-panel.test.tsx` 中已有的 ASR 测试数据结构（第 55-88 行）不变；
   若添加新的快照测试，需在 mock 数据中补充 `api_key_set` 字段，
   LLM 默认 `true`，Embedding 和 MinerU 按当前测试场景决定值。
