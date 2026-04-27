# 05 · 配置层变更

本文描述 `document_processing.yaml` 的新增配置项，以及 `processor.py` 中新参数的读取与透传逻辑。

---

## `document_processing.yaml` 变更

目标文件：[newbee_notebook/configs/document_processing.yaml](../../../newbee_notebook/configs/document_processing.yaml)

### 完整 diff

```diff
  document_processing:
    mineru_enabled: ${MINERU_ENABLED:true}
    mineru_mode: ${MINERU_MODE:cloud}

    mineru_cloud:
      api_key: ${MINERU_API_KEY:}
      api_base: ${MINERU_V4_API_BASE:https://mineru.net}
      timeout_seconds: ${MINERU_V4_TIMEOUT:120}
      poll_interval: ${MINERU_V4_POLL_INTERVAL:5}
      max_wait_seconds: ${MINERU_V4_MAX_WAIT_SECONDS:1800}
      cdn_curl_fallback_enabled: ${MINERU_CDN_CURL_FALLBACK_ENABLED:true}
      cdn_curl_binary: ${MINERU_CDN_CURL_BINARY:curl}
      cdn_curl_insecure: ${MINERU_CDN_CURL_INSECURE:false}
+     # MinerU v4 解析引擎选择：pipeline（默认）/ vlm（推荐，精度更高）/ MinerU-HTML（仅 HTML 文件）
+     # 留空则不传字段，由 API 使用默认值（等同于 pipeline）
+     model_version: ${MINERU_CLOUD_MODEL_VERSION:}
+     # 公式识别（关闭可加速无公式文档的处理）
+     enable_formula: ${MINERU_CLOUD_ENABLE_FORMULA:true}
+     # 表格识别
+     enable_table: ${MINERU_CLOUD_ENABLE_TABLE:true}
+     # 强制 OCR 开关：留空 = API 自动判断；true = 强制 OCR；false = 强制关闭 OCR
+     is_ocr: ${MINERU_CLOUD_IS_OCR:}
+     # OCR 语言，默认 ch（中英文），与本地模式保持一致
+     language: ${MINERU_CLOUD_LANGUAGE:ch}

    mineru_local:
      api_url: ${MINERU_LOCAL_API_URL:http://mineru-api:8000}
      backend: ${MINERU_BACKEND:pipeline}
      lang_list: ${MINERU_LANG_LIST:ch,en}
      timeout_seconds: ${MINERU_LOCAL_TIMEOUT:0}
      max_pages_per_batch: ${MINERU_LOCAL_MAX_PAGES_PER_BATCH:50}
      request_retry_attempts: ${MINERU_LOCAL_REQUEST_RETRY_ATTEMPTS:2}
      retry_backoff_seconds: ${MINERU_LOCAL_RETRY_BACKOFF_SECONDS:10}
      return_images: ${MINERU_LOCAL_RETURN_IMAGES:true}
      return_content_list: ${MINERU_LOCAL_RETURN_CONTENT_LIST:true}
      return_model_output: ${MINERU_LOCAL_RETURN_MODEL_OUTPUT:true}
+     # PDF 解析策略：auto（默认）/ txt（文本层 PDF，快）/ ocr（强制 OCR，扫描件）
+     parse_method: ${MINERU_LOCAL_PARSE_METHOD:auto}
+     # 公式识别开关
+     formula_enable: ${MINERU_LOCAL_FORMULA_ENABLE:true}
+     # 表格识别开关
+     table_enable: ${MINERU_LOCAL_TABLE_ENABLE:true}

    fail_threshold: ${MINERU_FAIL_THRESHOLD:5}
    cooldown_seconds: ${MINERU_COOLDOWN_SECONDS:120}
    documents_dir: ${DOCUMENTS_DIR:data/documents}
```

### 新增环境变量一览

#### 云端（`mineru_cloud`）

| 环境变量 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `MINERU_CLOUD_MODEL_VERSION` | string | `""` | 不设置 = API 自动（pipeline）；可设为 `vlm` 或 `MinerU-HTML` |
| `MINERU_CLOUD_ENABLE_FORMULA` | bool | `true` | 公式识别 |
| `MINERU_CLOUD_ENABLE_TABLE` | bool | `true` | 表格识别 |
| `MINERU_CLOUD_IS_OCR` | bool/空 | `""` | 不设置 = API 自动；`true`/`false` = 强制开关 |
| `MINERU_CLOUD_LANGUAGE` | string | `ch` | OCR 语言 |

#### 本地（`mineru_local`）

| 环境变量 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `MINERU_LOCAL_PARSE_METHOD` | string | `auto` | `auto` / `txt` / `ocr` |
| `MINERU_LOCAL_FORMULA_ENABLE` | bool | `true` | 公式识别 |
| `MINERU_LOCAL_TABLE_ENABLE` | bool | `true` | 表格识别 |

---

## `processor.py` 变更

目标文件：[newbee_notebook/infrastructure/document_processing/processor.py](../../../newbee_notebook/infrastructure/document_processing/processor.py)

### Cloud 部分（第 86-112 行）

```diff
              cloud_cfg = dp_cfg.get("mineru_cloud", {}) or {}
              api_key = str(cloud_cfg.get("api_key", "") or "").strip()
              if api_key:
                  try:
+                     # 空字符串 → None（避免向 API 发送空字段）
+                     _model_version = str(cloud_cfg.get("model_version", "") or "").strip() or None
+                     _is_ocr_raw = str(cloud_cfg.get("is_ocr", "") or "").strip()
+                     _is_ocr = _parse_bool(_is_ocr_raw, None) if _is_ocr_raw else None
                      converters.append(
                          MinerUCloudConverter(
                              api_key=api_key,
                              api_base=str(cloud_cfg.get("api_base", "https://mineru.net")),
                              timeout_seconds=_parse_int(cloud_cfg.get("timeout_seconds"), 60),
                              poll_interval=_parse_int(cloud_cfg.get("poll_interval"), 5),
                              max_wait_seconds=_parse_int(cloud_cfg.get("max_wait_seconds"), 1800),
                              enable_curl_fallback=_parse_bool(
                                  cloud_cfg.get("cdn_curl_fallback_enabled"), True,
                              ),
                              curl_binary=str(cloud_cfg.get("cdn_curl_binary", "curl")),
                              curl_insecure=_parse_bool(cloud_cfg.get("cdn_curl_insecure"), False),
+                             model_version=_model_version,
+                             enable_formula=_parse_bool(cloud_cfg.get("enable_formula"), True),
+                             enable_table=_parse_bool(cloud_cfg.get("enable_table"), True),
+                             is_ocr=_is_ocr,
+                             language=str(cloud_cfg.get("language", "ch") or "ch"),
                          )
                      )
```

**`_is_ocr` 的解析逻辑**：

YAML 里 `${MINERU_CLOUD_IS_OCR:}` 默认解析为空字符串。处理步骤：
1. 读取原始字符串 `_is_ocr_raw`
2. 若为空字符串 → `_is_ocr = None`（不传给 API）
3. 若非空 → 用 `_parse_bool` 解析为 `True`/`False`

`_parse_bool` 已有处理空字符串的逻辑（返回 `default`），但现有签名是 `_parse_bool(value, default: bool)` — `default` 类型是 `bool`，无法接受 `None`。因此用条件表达式处理：

```python
_is_ocr = _parse_bool(_is_ocr_raw, None) if _is_ocr_raw else None
```

> 如果 `_parse_bool` 的类型注解不允许 `None` 作为 default，可以在 `processor.py` 里内联一个私有辅助函数，或直接用 `{"true": True, "false": False, "1": True, "0": False}.get(_is_ocr_raw.lower())` 替代。

### Local 部分（第 119-139 行）

```diff
              local_cfg = dp_cfg.get("mineru_local", {}) or {}
              converters.append(
                  MinerULocalConverter(
                      base_url=str(local_cfg.get("api_url", "http://mineru-api:8000")),
                      timeout_seconds=_parse_int(local_cfg.get("timeout_seconds"), 0),
                      backend=str(local_cfg.get("backend", "pipeline")),
                      lang_list=str(local_cfg.get("lang_list", "ch,en")),
                      return_images=_parse_bool(local_cfg.get("return_images"), True),
                      return_content_list=_parse_bool(local_cfg.get("return_content_list"), True),
                      return_model_output=_parse_bool(local_cfg.get("return_model_output"), True),
                      max_pages_per_batch=_parse_int(local_cfg.get("max_pages_per_batch"), 50),
                      request_retry_attempts=_parse_int(
                          local_cfg.get("request_retry_attempts"), 2,
                      ),
                      retry_backoff_seconds=_parse_float(
                          local_cfg.get("retry_backoff_seconds"), 10.0,
                      ),
+                     parse_method=str(local_cfg.get("parse_method", "auto") or "auto"),
+                     formula_enable=_parse_bool(local_cfg.get("formula_enable"), True),
+                     table_enable=_parse_bool(local_cfg.get("table_enable"), True),
                  )
              )
```

---

## 配置优先级说明

系统配置读取遵循以下优先级（高到低）：

```
环境变量（.env 或 docker-compose environment）
  ↓
YAML 配置文件（document_processing.yaml）
  ↓
代码内默认值（__init__ 参数默认值）
```

YAML 里的 `${VAR:default}` 占位符由 `config.py` 的 `_resolve_env_var` 处理：
- 若 `VAR` 存在于环境中 → 使用环境变量值
- 否则 → 使用 `:` 后的 default 值

**实操建议**：本地开发时通过 `.env` 文件覆盖参数；生产环境通过 `docker-compose.yml` 或 `docker-compose.gpu.yml` 的 `environment:` 块设置。

---

## 验收方式

```bash
# 验证配置读取正常（无新参数时使用默认值）
python -c "
from newbee_notebook.core.common.config import get_document_processing_config
cfg = get_document_processing_config()
dp = cfg.get('document_processing', {})

# 云端新参数
cloud = dp.get('mineru_cloud', {})
print('cloud model_version:', repr(cloud.get('model_version')))
print('cloud enable_formula:', cloud.get('enable_formula'))
print('cloud language:', cloud.get('language'))

# 本地新参数
local = dp.get('mineru_local', {})
print('local parse_method:', local.get('parse_method'))
print('local formula_enable:', local.get('formula_enable'))
print('local table_enable:', local.get('table_enable'))
"
# 期望输出：
# cloud model_version: ''    （空字符串，会在 processor.py 中转 None）
# cloud enable_formula: 'true'
# cloud language: 'ch'
# local parse_method: 'auto'
# local formula_enable: 'true'
# local table_enable: 'true'
```
