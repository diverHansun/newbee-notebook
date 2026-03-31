# 问题分析 - API Key 状态指示器统一补全

## 一、当前状态

### 1.1 ASR：已有完整实现

**后端** `newbee_notebook/api/routers/config.py`

`ASRConfigResponse`（第 54-58 行）含 `api_key_set: bool` 字段。

`get_models_config()`（第 150-177 行）在组装响应时，调用
`resolve_asr_api_key(asr["provider"])` 并将结果转为布尔值后写入：

```python
asr_api_key = resolve_asr_api_key(asr["provider"])
asr=ASRConfigResponse(
    provider=asr["provider"],
    model=asr["model"],
    source=asr["source"],
    api_key_set=bool(asr_api_key),
)
```

`resolve_asr_api_key`（`config_db.py` 第 460-466 行）：

```python
def resolve_asr_api_key(provider: str) -> str | None:
    normalized = str(provider or "").strip().lower()
    if normalized == "zhipu":
        return os.getenv("ZHIPU_API_KEY")
    if normalized == "qwen":
        return os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
    return None
```

校验方式：仅检查对应环境变量是否非空，不调用远端 API 验证有效性。

**前端** `frontend/src/lib/api/config.ts`

`ASRConfig` 接口（第 20-25 行）含 `api_key_set: boolean`。

**前端** `frontend/src/components/layout/model-config-panel.tsx`

`ASRDraft` 类型（第 43-47 行）含 `api_key_set: boolean`。

`toASRDraft()`（第 98-104 行）将 `config.api_key_set` 写入 draft。

UI 渲染（第 682-701 行）：一个只读行显示状态圆点与文字，key 未配置时额外渲染一个警告块。

---

### 1.2 LLM：无任何 API key 检查

**后端**

`LLMConfigResponse`（`config.py` 第 37-43 行）：无 `api_key_set` 字段。

`get_models_config()` 在组装 LLM 部分时直接 `LLMConfigResponse(**llm)`，
未调用任何 key 检查函数。

`config_db.py` 中不存在 `resolve_llm_api_key` 函数。

**前端**

`LLMConfig` 接口（`config.ts` 第 3-10 行）：无 `api_key_set` 字段。

`LLMDraft` 类型（`model-config-panel.tsx` 第 27-33 行）：无 `api_key_set` 字段。

LLM 配置卡片 UI 中无状态指示器渲染。

**LLM 涉及的 API key**

| provider | 环境变量 |
|---|---|
| zhipu | `ZHIPU_API_KEY` |
| qwen  | `DASHSCOPE_API_KEY` |

LLM 是整个系统最核心的依赖，provider 对应的 key 若未配置，所有对话功能均不可用，
但用户在配置面板中无法获知这一情况。

---

### 1.3 Embedding：无任何 API key 检查

**后端**

`EmbeddingConfigResponse`（`config.py` 第 46-51 行）：无 `api_key_set` 字段。

`get_models_config()` 组装 Embedding 部分时未调用任何 key 检查函数。

`config_db.py` 中不存在 `resolve_embedding_api_key` 函数。

**前端**

`EmbeddingConfig` 接口（`config.ts` 第 12-18 行）：无 `api_key_set` 字段。

`EmbeddingDraft` 类型（`model-config-panel.tsx` 第 35-41 行）：无 `api_key_set` 字段。

**Embedding 涉及的 API key 与模式关系**

Embedding 配置中存在"是否需要 API key"随模式变化的情况：

| provider | mode | 所需环境变量 |
|---|---|---|
| qwen3-embedding | api | `DASHSCOPE_API_KEY` |
| qwen3-embedding | local | 无（使用本地模型文件） |
| zhipu | 无 mode 区分 | `ZHIPU_API_KEY` |

`config_db.py` 第 303-353 行中，`get_embedding_config_async()` 在 provider 为
`qwen3-embedding` 时通过 `mode` 字段区分 api/local，并决定使用哪个模型路径。

local 模式下不依赖任何 API key，状态指示器对其无意义，因此需要区分处理。

---

### 1.4 MinerU：无任何 API key 检查

**后端**

`MinerUConfigResponse`（`config.py` 第 61-64 行）：无 `api_key_set` 字段。

`get_models_config()` 组装 MinerU 部分时未调用任何 key 检查函数。

`config_db.py` 中不存在 `resolve_mineru_api_key` 函数。

**前端**

`MinerUConfig` 接口（`config.ts` 第 27-31 行）：无 `api_key_set` 字段。

`MinerUDraft` 类型（`model-config-panel.tsx` 第 49-53 行）：无 `api_key_set` 字段。

**MinerU 涉及的 API key 与模式关系**

| mode | 所需环境变量 |
|---|---|
| cloud | `MINERU_API_KEY` |
| local | 无（使用本地 mineru-api 服务） |

`.env.example` 第 157 行：`MINERU_API_KEY=`（cloud 模式必填，local 模式无需）。

local 模式下状态指示器对 MinerU 同样无意义，需区分处理。

---

## 二、问题总结

| 配置项 | 后端 api_key_set 字段 | 前端类型 api_key_set | UI 状态指示器 |
|---|:---:|:---:|:---:|
| ASR | 有 | 有 | 有 |
| LLM | 无 | 无 | 无 |
| Embedding | 无 | 无 | 无 |
| MinerU | 无 | 无 | 无 |

LLM 缺少指示器的影响最大：key 未配置时系统无法正常工作，但配置面板中无任何提示。

Embedding 和 MinerU 的情况类似，且均存在"某些模式下不需要 API key"的特殊性，
设计时需要处理"不适用"（not applicable）这一状态，避免在不需要 key 的模式下显示误导性信息。
