# 04 · 云端转换器变更（MinerUCloudConverter）

本文描述 `MinerUCloudConverter` 在 MinerU 3.0 适配中的代码变更：补全 v4 API 新增的五个参数，以及 `model_version` 三种模式的详细说明。

---

## 官方依据

来源：<https://mineru.net/apiManage/docs>，`POST /api/v4/file-urls/batch` 请求体定义：

```json
{
  "files": [
    {
      "name": "string (必填)",
      "data_id": "string",
      "is_ocr": "boolean",
      "page_ranges": "string"
    }
  ],
  "model_version": "pipeline | vlm | MinerU-HTML",
  "enable_formula": "boolean",
  "enable_table": "boolean",
  "language": "string",
  "callback": "string",
  "seed": "string",
  "extra_formats": ["docx", "html", "latex"]
}
```

当前实现（`_request_upload_url`）只传了 `files[0].name`，缺少其余所有参数。

---

## `model_version` 三种模式详解

`model_version` 是本轮云端侧最关键的新参数，决定了 MinerU 后端使用哪套解析引擎。

### pipeline

- **定位**：标准 OCR 管道，不指定 `model_version` 时的 API **默认值**
- **原理**：传统检测模型（Layout 检测 + OCR 引擎）流水线处理
- **适用场景**：通用文档、纯文字 PDF、结构简单的报告；速度最快
- **不适合**：复杂多栏版式、大量数学公式、精细表格、图表密集文档

### vlm（官方推荐）

- **定位**：视觉语言模型（Vision Language Model），官方文档标注"推荐"
- **原理**：大型多模态模型对页面图像整体理解，而非逐组件拼装
- **适用场景**：复杂版式文档（多栏、学术论文、图文混排）、数学公式密集、表格结构复杂；精度最高
- **代价**：处理耗时更长，API 配额消耗与 pipeline 相同（官方未披露差异），但对于相同 200 页的限制，复杂文档用 vlm 效果更好

### MinerU-HTML

- **定位**：专用于 HTML 文件解析
- **重要限制**：**只能用于 HTML 文件**，官方文档明确说明"如果解析文件为 HTML 文件，`model_version` 需要明确指定为 `MinerU-HTML`"
- **当前代码的 `can_handle`**：`MinerUCloudConverter` 的 `SUPPORTED_EXTENSIONS = frozenset({".pdf", ".doc", ".docx"})`，目前不处理 HTML 文件，所以 `MinerU-HTML` 当前没有实际用途；保留配置项是为了未来扩展

### 推荐配置策略

| 场景 | 推荐值 | 原因 |
|---|---|---|
| 默认生产环境 | 不设置（`None`） | 使用 API 默认（pipeline），稳定、快速 |
| 学术论文 / 复杂 PDF | `vlm` | 公式、多栏版式效果显著更好 |
| 以 HTML 为主 | `MinerU-HTML` | 强制要求，其他模式无法正确解析 HTML |

**关于不在前端暴露**：`model_version` 属于影响 API 配额消耗和解析精度的运维级参数，不应由普通用户随意切换，因此仅在 `document_processing.yaml` 中配置（或通过 `MINERU_CLOUD_MODEL_VERSION` 环境变量设置），不接入前端 Settings Panel。

---

## 新增参数说明

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `model_version` | `str \| None` | `None` | 解析引擎选择；`None` 表示不传字段（使用 API 默认） |
| `enable_formula` | `bool` | `True` | 公式识别开关 |
| `enable_table` | `bool` | `True` | 表格识别开关 |
| `is_ocr` | `bool \| None` | `None` | `None` 表示不传（API 自动判断）；`True` 强制 OCR；`False` 强制关闭 OCR |
| `language` | `str` | `"ch"` | OCR 语言；与本地模式 `lang_list` 的首项保持一致 |

**`None` 语义**：`model_version` 和 `is_ocr` 使用 `None` 而非默认字符串，在构建 payload 时会被跳过（不发送该字段），让 API 服务端使用自己的默认值。这样未来 MinerU 调整默认行为时，我们无需改代码。

---

## 代码变更

### `mineru_cloud_converter.py` — 构造器扩展

目标文件：[newbee_notebook/infrastructure/document_processing/converters/mineru_cloud_converter.py](../../../newbee_notebook/infrastructure/document_processing/converters/mineru_cloud_converter.py)

```diff
  class MinerUCloudConverter(Converter):

      def __init__(
          self,
          api_key: str,
          api_base: str = "https://mineru.net",
          timeout_seconds: int = 60,
          poll_interval: int = 5,
          max_wait_seconds: int = 1800,
          enable_curl_fallback: bool = True,
          curl_binary: str = "curl",
          curl_insecure: bool = False,
+         model_version: Optional[str] = None,
+         enable_formula: bool = True,
+         enable_table: bool = True,
+         is_ocr: Optional[bool] = None,
+         language: str = "ch",
      ) -> None:
          # ... 现有验证逻辑不变 ...
          self._api_key = key
          self._api_base = api_base.rstrip("/")
          self._timeout_seconds = int(timeout_seconds)
          self._poll_interval = int(poll_interval)
          self._max_wait_seconds = int(max_wait_seconds)
          self._connect_timeout_seconds = 5
          self._enable_curl_fallback = bool(enable_curl_fallback)
          self._curl_binary = (curl_binary or "curl").strip() or "curl"
          self._curl_insecure = bool(curl_insecure)
+         self._model_version = (model_version or "").strip() or None
+         self._enable_formula = bool(enable_formula)
+         self._enable_table = bool(enable_table)
+         self._is_ocr = is_ocr  # None 表示不传字段
+         self._language = (language or "ch").strip() or "ch"
```

> `self._model_version = (model_version or "").strip() or None`：将空字符串（来自 YAML `${MINERU_CLOUD_MODEL_VERSION:}`）统一转为 `None`，避免向 API 发送空字符串导致 400 错误。

### `mineru_cloud_converter.py` — `_request_upload_url` payload 扩展

```diff
  def _request_upload_url(self, file_name: str) -> tuple[str, str]:
      url = f"{self._api_base}/api/v4/file-urls/batch"
-     payload = {"files": [{"name": file_name}]}
+     file_entry: dict = {"name": file_name}
+     if self._is_ocr is not None:
+         file_entry["is_ocr"] = self._is_ocr
+
+     payload: dict = {"files": [file_entry]}
+     if self._model_version:
+         payload["model_version"] = self._model_version
+     payload["enable_formula"] = self._enable_formula
+     payload["enable_table"] = self._enable_table
+     payload["language"] = self._language
+
      headers = self._headers()
      headers["Content-Type"] = "application/json"

      response = requests.post(url, headers=headers, json=payload, timeout=self._api_timeout())
```

**payload 构建策略**：

- `model_version`：仅在非 `None` 时加入 payload（避免空字段）
- `is_ocr`：放在 `files[0]` 对象里（官方 API 规范要求每个文件单独指定）
- `enable_formula` / `enable_table` / `language`：作为顶层字段，始终传（值就是配置的布尔/字符串）

---

## 不需要修改的部分

### 云端 ZIP 解析（`_parse_result_zip`）

云端 `full.md` 在 v4 API 输出中路径结构与 2.7 一致（顶层直接有 `full.md`），当前云端 `_parse_result_zip` 的逻辑：

```python
markdown_path = next((n for n in md_candidates if n.lower().endswith("/full.md")), md_candidates[0])
```

优先找 `full.md`，找不到退而求其次取第一个 `.md`。v4 API 的 ZIP 中始终包含 `full.md`，此逻辑无需变化。

### CDN 下载 fallback 逻辑

`_download_zip` → `_download_zip_with_curl` 的 SSL 故障降级路径、`MinerUCloudTransientError` 的 circuit breaker 触发语义，均与 v4 API 的新参数无关，不动。

---

## 验收方式

```bash
# 验证构造器接受新参数
python -c "
from newbee_notebook.infrastructure.document_processing.converters.mineru_cloud_converter import MinerUCloudConverter
c = MinerUCloudConverter(
    api_key='test-key',
    model_version='vlm',
    enable_formula=True,
    enable_table=True,
    is_ocr=None,
    language='ch',
)
print('model_version:', c._model_version)
print('is_ocr:', c._is_ocr)
print('Constructor OK')
"

# 验证空字符串 model_version 被正确转为 None
python -c "
from newbee_notebook.infrastructure.document_processing.converters.mineru_cloud_converter import MinerUCloudConverter
c = MinerUCloudConverter(api_key='test', model_version='')
assert c._model_version is None, 'empty string should become None'
print('Empty model_version -> None: OK')
"
```
