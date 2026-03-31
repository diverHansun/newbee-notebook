# 设计规范 - API Key 状态指示器统一补全

## 一、API key 映射规则

各配置项与环境变量的对应关系，以及是否需要显示指示器：

### LLM

| provider | 检查的环境变量 | 是否显示指示器 |
|---|---|:---:|
| zhipu | `ZHIPU_API_KEY` | 始终显示 |
| qwen  | `DASHSCOPE_API_KEY` | 始终显示 |

LLM 不存在"不需要 key"的模式，指示器始终显示。

### Embedding

| provider | mode | 检查的环境变量 | 是否显示指示器 |
|---|---|---|:---:|
| qwen3-embedding | api | `DASHSCOPE_API_KEY` | 显示 |
| qwen3-embedding | local | 无 | 不显示 |
| zhipu | — | `ZHIPU_API_KEY` | 显示 |

mode=local 时不依赖任何 API key，不显示指示器（`api_key_set` 返回 `None`）。

### MinerU

| mode | 检查的环境变量 | 是否显示指示器 |
|---|---|:---:|
| cloud | `MINERU_API_KEY` | 显示 |
| local | 无 | 不显示 |

mode=local 时不显示指示器（`api_key_set` 返回 `None`）。

---

## 二、后端字段设计

### Response 类型变更

**LLMConfigResponse**（`config.py` 第 37-43 行）

新增字段：

```python
api_key_set: bool
```

**EmbeddingConfigResponse**（`config.py` 第 46-51 行）

新增字段：

```python
api_key_set: bool | None = None
```

`None` 表示当前配置模式下不需要 API key，前端据此决定是否渲染指示器。

**MinerUConfigResponse**（`config.py` 第 61-64 行）

新增字段：

```python
api_key_set: bool | None = None
```

含义同上。

### 新增 resolve 函数

在 `config_db.py` 中，紧跟 `resolve_asr_api_key`（第 460-466 行）之后新增三个函数：

**resolve_llm_api_key**

```python
def resolve_llm_api_key(provider: str) -> str | None:
    normalized = str(provider or "").strip().lower()
    if normalized == "zhipu":
        return os.getenv("ZHIPU_API_KEY")
    if normalized == "qwen":
        return os.getenv("DASHSCOPE_API_KEY")
    return None
```

**resolve_embedding_api_key**

```python
def resolve_embedding_api_key(provider: str, mode: str | None) -> str | None:
    """
    返回 None 表示当前配置不需要 API key（local 模式），
    返回空字符串或 None（falsy）表示需要但未配置。
    使用 sentinel 区分：返回字符串 "__not_applicable__" 表示不适用。
    """
    normalized_provider = str(provider or "").strip().lower()
    if normalized_provider == "qwen3-embedding":
        if str(mode or "").strip().lower() == "local":
            return "__not_applicable__"
        return os.getenv("DASHSCOPE_API_KEY")
    if normalized_provider == "zhipu":
        return os.getenv("ZHIPU_API_KEY")
    return None
```

调用侧转换：

```python
raw = resolve_embedding_api_key(provider, mode)
api_key_set = None if raw == "__not_applicable__" else bool(raw)
```

**resolve_mineru_api_key**

```python
def resolve_mineru_api_key(mode: str) -> str | None:
    """
    返回 "__not_applicable__" 表示 local 模式不需要 API key。
    """
    if str(mode or "").strip().lower() == "local":
        return "__not_applicable__"
    return os.getenv("MINERU_API_KEY")
```

调用侧转换同上。

---

## 三、前端类型变更

### config.ts 接口更新

**LLMConfig**（第 3-10 行）新增：

```typescript
api_key_set: boolean;
```

**EmbeddingConfig**（第 12-18 行）新增：

```typescript
api_key_set: boolean | null;
```

`null` 对应后端 `None`，表示当前模式不适用。

**MinerUConfig**（第 27-31 行）新增：

```typescript
api_key_set: boolean | null;
```

### model-config-panel.tsx 类型更新

**LLMDraft**（第 27-33 行）新增：

```typescript
api_key_set: boolean;
```

**EmbeddingDraft**（第 35-41 行）新增：

```typescript
api_key_set: boolean | null;
```

**MinerUDraft**（第 49-53 行）新增：

```typescript
api_key_set: boolean | null;
```

对应的 `toLLMDraft()`、`toEmbeddingDraft()`、`toMinerUDraft()` 函数各增加
`api_key_set: config.api_key_set` 一行。

---

## 四、UI 呈现规范

### 呈现规则

- `api_key_set === null`：不渲染指示器（当前模式不需要 key）
- `api_key_set === true`：显示绿色圆点 + "已配置"
- `api_key_set === false`：显示灰色圆点 + "未配置"

### 与 ASR 的差异

ASR 现有实现在 `api_key_set === false` 时额外渲染了一个 `control-panel-warning` 块
（`model-config-panel.tsx` 第 697-701 行），内容与状态行重复。

LLM、Embedding、MinerU 新增的指示器不加这个警告块，只保留状态行，保持简洁。

### 状态行 HTML 结构

与 ASR 保持一致，复用已有 CSS 类：

```tsx
{draft.api_key_set !== null && (
  <div className="control-panel-readonly-row">
    <span className="control-panel-readonly-label">
      {t(uiStrings.controlPanel.apiKeyStatus)}
    </span>
    <span className="control-panel-status">
      <span
        className={`control-panel-status-dot${draft.api_key_set ? " is-ok" : ""}`}
        aria-hidden="true"
      />
      <span>
        {draft.api_key_set
          ? t(uiStrings.controlPanel.apiKeyConfigured)
          : t(uiStrings.controlPanel.apiKeyMissing)}
      </span>
    </span>
  </div>
)}
```

### i18n 字符串

新增三条共用字符串，供 LLM、Embedding、MinerU 统一使用（区别于 ASR 的专用字符串）：

```typescript
apiKeyStatus:     { zh: "API Key", en: "API key" },
apiKeyConfigured: { zh: "已配置",  en: "Configured" },
apiKeyMissing:    { zh: "未配置",  en: "Not configured" },
```

字符串尽量短，与 ASR 现有的 `asrApiKeyStatus` / `asrApiKeyConfigured` / `asrApiKeyMissing`
并列存放，不替换。

---

## 五、放置位置

UI 中各配置卡片内，状态行放在该卡片最后一个可编辑字段之后、卡片结束 `</div>` 之前，
与 ASR 中状态行所处位置一致（ASR 状态行在 model 输入字段之后，第 682 行）。
