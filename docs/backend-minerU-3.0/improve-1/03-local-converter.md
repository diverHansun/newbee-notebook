# 03 · 本地转换器变更（MinerULocalConverter）

本文描述 `MinerULocalConverter` 在 MinerU 3.0 适配中的代码变更：新增三个构造器参数，并在实际请求的 `form_data` 中透传给本地 API。

---

## 官方依据

`mineru/mineru/cli/fast_api.py` 第 795-823 行（新版 `/file_parse` Form 参数定义）：

```python
backend: Annotated[str, Form(description="""
- pipeline: ...
- vlm-auto-engine: ...
- hybrid-auto-engine: ...
- hybrid-http-client: ...""")] = "hybrid-auto-engine",

parse_method: Annotated[str, Form(description="""
- auto: Automatically determine the method based on the file type
- txt: Use text extraction method
- ocr: Use OCR method for image-based PDFs""")] = "auto",

formula_enable: Annotated[bool, Form(description="Enable formula parsing.")] = True,

table_enable: Annotated[bool, Form(description="Enable table parsing.")] = True,
```

这三个参数在 2.7.x 版本中不存在；3.0 起可以显式控制，不传则使用 API 默认值（`auto` / `True` / `True`）。

---

## 新增参数说明

### `parse_method: str = "auto"`

控制 PDF 的解析策略，**仅对 `pipeline` 和 `hybrid` backend 有效**。

| 值 | 使用场景 |
|---|---|
| `auto` | 默认值，MinerU 根据 PDF 内容（是否有可抽取文本层）自动判断；大多数情况下使用这个 |
| `txt` | PDF 有文本层（非扫描件），直接抽取文字，速度最快、无幻觉风险 |
| `ocr` | 强制走 OCR 路径，适合扫描件或文本层损坏的 PDF；速度最慢 |

环境变量：`MINERU_LOCAL_PARSE_METHOD`（默认 `auto`）

### `formula_enable: bool = True`

数学公式识别开关。

- 开启（默认）：识别 LaTeX 公式，输出 `$...$` 或 `$$...$$` 格式
- 关闭：公式区域当作普通文字处理，适合对公式无需求的文档（可加速处理）

环境变量：`MINERU_LOCAL_FORMULA_ENABLE`（默认 `true`）

### `table_enable: bool = True`

表格识别开关。

- 开启（默认）：识别表格，输出 Markdown 表格格式
- 关闭：表格区域当作普通文字处理

环境变量：`MINERU_LOCAL_TABLE_ENABLE`（默认 `true`）

---

## 代码变更

### `mineru_local_converter.py` — 构造器扩展

目标文件：[newbee_notebook/infrastructure/document_processing/converters/mineru_local_converter.py](../../../newbee_notebook/infrastructure/document_processing/converters/mineru_local_converter.py)

```diff
  class MinerULocalConverter(Converter):
      """Converter for PDFs via MinerU local HTTP API."""

      def __init__(
          self,
          base_url: Optional[str] = None,
          timeout_seconds: int = 300,
          backend: str = "pipeline",
          lang_list: str = "ch,en",
          return_images: bool = True,
          return_content_list: bool = True,
          return_model_output: bool = True,
          max_pages_per_batch: int = _DEFAULT_MAX_PAGES_PER_BATCH,
          request_retry_attempts: int = _DEFAULT_REQUEST_RETRY_ATTEMPTS,
          retry_backoff_seconds: float = _DEFAULT_RETRY_BACKOFF_SECONDS,
+         parse_method: str = "auto",
+         formula_enable: bool = True,
+         table_enable: bool = True,
      ) -> None:
          self._base_url = (base_url or "http://mineru-api:8000").rstrip("/")
          self._timeout = timeout_seconds
          self._backend = backend
          self._lang_list = lang_list
          self._return_images = return_images
          self._return_content_list = return_content_list
          self._return_model_output = return_model_output
          self._max_pages_per_batch = max(1, max_pages_per_batch)
          self._request_retry_attempts = max(0, request_retry_attempts)
          self._retry_backoff_seconds = max(0.0, retry_backoff_seconds)
+         self._parse_method = parse_method
+         self._formula_enable = formula_enable
+         self._table_enable = table_enable
```

### `mineru_local_converter.py` — `_convert_range` 透传

在 `_convert_range` 方法中，将新参数加入 `form_data`：

```diff
      async def _convert_range(self, path, *, start_page, end_page, total_pages):
          url = f"{self._base_url}/file_parse"

          form_data: list[tuple[str, str]] = [
              ("backend", self._backend),
              ("return_md", "true"),
              ("return_content_list", "true" if self._return_content_list else "false"),
              ("return_model_output", "true" if self._return_model_output else "false"),
              ("return_images", "true" if self._return_images else "false"),
              ("response_format_zip", "true"),
              ("start_page_id", str(start_page)),
              ("end_page_id", str(end_page)),
+             ("parse_method", self._parse_method),
+             ("formula_enable", "true" if self._formula_enable else "false"),
+             ("table_enable", "true" if self._table_enable else "false"),
          ]
          for language in self._normalize_lang_list(self._lang_list):
              form_data.append(("lang_list", language))
```

> **注意**：`parse_method` 在 MinerU fast_api 里对 `vlm-*` 系列 backend 无效（只对 pipeline 和 hybrid 有效），但传了也不会报错，API 会直接忽略。我们统一传，保持 form_data 结构简洁。

---

## 不需要修改的部分

### `_parse_result_zip` — 兼容新 ZIP 结构，无需改动

MinerU 3.0 的 ZIP 内路径从单层变成两层嵌套：

```
# 旧版（2.7.x）
paper.md
images/fig1.png
paper_content_list_v2.json

# 新版（3.0+）
paper/paper_hybrid-auto-engine_auto/paper.md
paper/paper_hybrid-auto-engine_auto/images/fig1.png
paper/paper_hybrid-auto-engine_auto/paper_content_list_v2.json
```

当前 `_parse_result_zip` 的前缀检测逻辑（[mineru_local_converter.py:307-328](../../../newbee_notebook/infrastructure/document_processing/converters/mineru_local_converter.py#L307-L328)）：

```python
markdown_path = md_candidates[0]
root_prefix = str(PurePosixPath(markdown_path).parent)
if root_prefix in {"", "."}:
    root_prefix = ""
prefix = f"{root_prefix}/" if root_prefix else ""
```

用新版 ZIP 路径验证：
- `markdown_path = "paper/paper_hybrid-auto-engine_auto/paper.md"`
- `root_prefix = "paper/paper_hybrid-auto-engine_auto"`
- `prefix = "paper/paper_hybrid-auto-engine_auto/"`

对 `paper/paper_hybrid-auto-engine_auto/images/fig1.png`：
- `rel = name[len(prefix):]` = `"images/fig1.png"` ✓（正确归类到 `image_assets`）

对 `paper/paper_hybrid-auto-engine_auto/paper_content_list_v2.json`：
- `rel = "paper_content_list_v2.json"` ✓（正确归类到 `metadata_assets`）

`_extract_page_count` 的 `lower_name.endswith("content_list_v2.json")` 检查对相对路径也有效 ✓

**结论：无需修改，需在验收时实际跑一次确认。**

---

## 参数兼容性矩阵

| 参数 | pipeline | hybrid-auto-engine | vlm-auto-engine | 说明 |
|---|---|---|---|---|
| `parse_method` | ✓ 有效 | ✓ 有效 | ✗ 忽略 | 官方文档注明仅 pipeline/hybrid 支持 |
| `formula_enable` | ✓ 有效 | ✓ 有效 | ✓ 有效 | 全 backend 支持 |
| `table_enable` | ✓ 有效 | ✓ 有效 | ✓ 有效 | 全 backend 支持 |

`docker-compose.gpu.yml` 中 `MINERU_BACKEND=hybrid-auto-engine`，三个参数都完全生效。

---

## 验收方式

```bash
# 验证新参数被正确透传：用 OCR 模式解析一份已知扫描件 PDF
# 先临时设置 MINERU_LOCAL_PARSE_METHOD=ocr，观察 log 中的 form_data

# 验证 formula_enable=false 时公式区域被跳过
# 验证 table_enable=false 时表格区域被跳过

# 用新版本跑已知样本，确认 ZIP 结构解析正确
python -c "
from newbee_notebook.infrastructure.document_processing.converters.mineru_local_converter import MinerULocalConverter
c = MinerULocalConverter(parse_method='auto', formula_enable=True, table_enable=True)
print('Constructor OK')
"
```
