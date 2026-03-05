# docx/doc/pptx 格式扩展方案

本文描述将 MinerU 云端转换器的支持格式从 `.pdf` 扩展至 Office 文档格式的具体方案。转换器架构背景见 [01-converter-architecture.md](01-converter-architecture.md)，API 格式支持详情见 [02-cloud-api.md](02-cloud-api.md)。

## 1. 现状与目标

**现状**：`MinerUCloudConverter.can_handle()` 只接受 `.pdf`，其他格式直接跳过，由 MarkItDown 处理。

**目标**：云端模式下，`.doc`、`.docx`、`.ppt`、`.pptx` 优先走 MinerU 云端解析，失败时 fallback 至 MarkItDown。本地模式行为不变。

**验证依据**：已于 2026-02-24 通过实际 docx 文件上传至 MinerU 云端 API 确认可用，详见 [02-cloud-api.md § 9](02-cloud-api.md)。

## 2. 改动点

改动范围仅在 `mineru_cloud_converter.py`，不影响其他 converter 和 processor。

### 2.1 can_handle 扩展

**文件**：`newbee_notebook/infrastructure/document_processing/converters/mineru_cloud_converter.py`

```python
# 现有实现
def can_handle(self, ext: str) -> bool:
    return ext.lower() == ".pdf"

# 改动后
_SUPPORTED_EXTENSIONS = frozenset({
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
})

def can_handle(self, ext: str) -> bool:
    return ext.lower() in _SUPPORTED_EXTENSIONS
```

### 2.2 页数计算适配

当前 `convert()` 末尾的 fallback 逻辑调用 `_count_pages(path)`，该方法使用 `PdfReader` 读取文件——对非 PDF 文件会抛出异常（内部已 try/except，返回 0）。

因此：对于 `.docx`/`.doc`/`.pptx`/`.ppt` 文件，`page_count` 将依赖 `layout.json` 中的 `pdf_info` 字段（MinerU 内部先转 PDF 再解析），`_extract_page_count` 已能正确处理。

当 `layout.json` 中无有效数据时，`page_count` 退化为 `0`。这是可接受的降级行为，不影响 markdown 提取。

**无需修改**：`_count_pages` 的 try/except 已覆盖该情况，返回 0 即可。

### 2.3 无需修改的部分

| 方法 | 理由 |
|------|------|
| `_request_upload_url` | 上传流程与格式无关，文件名后缀正确即可 |
| `_upload_file` | 二进制上传，无格式依赖 |
| `_poll_until_done` | 状态轮询与格式无关 |
| `_download_zip` | ZIP 下载与格式无关 |
| `_parse_result_zip` | ZIP 结构对 docx 和 PDF 一致（均含 full.md） |

## 3. 扩展后格式路由矩阵

| 格式 | cloud 模式主处理 | cloud 模式 fallback | local 模式 |
|------|-----------------|---------------------|-----------|
| `.pdf` | MinerUCloud | MarkItDown | MinerULocal -> MarkItDown |
| `.docx` / `.doc` | MinerUCloud（新增） | MarkItDown | MarkItDown |
| `.pptx` / `.ppt` | MinerUCloud（新增） | MarkItDown | MarkItDown |
| `.xlsx` / `.xls` | — | MarkItDown | MarkItDown |
| `.txt` / `.md` / `.csv` | — | MarkItDown | MarkItDown |
| `.html` / `.htm` | — | MarkItDown | MarkItDown |

## 4. 边界情况

**文件编码问题**：验证中发现 docx 内的智能引号（`'`、`"`）在 VLM 模型输出中出现乱码（如 `don't` 变为 `don't`）。这是 MinerU VLM 模型的已知行为，与格式支持无关，属于输出质量问题，可在后续迭代中评估是否后处理修正。

**转换失败时的 err_msg**：若 MinerU 内部 docx → PDF 转换失败，服务端返回 `state=failed`，`err_msg` 为 `"文件转换失败"`（错误码 -60015）。此时 `MinerUCloudConverter` 抛出 `RuntimeError`，processor 降级至 MarkItDown。

**本地 MinerU**：本地 Docker 服务（`/file_parse` 端点）硬编码拒绝非 PDF/图像格式，直接返回 HTTP 400。`MinerULocalConverter.can_handle()` 不需要修改，维持仅 `.pdf`。

## 5. 实施清单

| 编号 | 改动 | 文件 | 影响范围 |
|------|------|------|----------|
| 1 | 添加 `_SUPPORTED_EXTENSIONS` 常量 | `mineru_cloud_converter.py` | 仅该文件 |
| 2 | 修改 `can_handle()` 引用常量 | `mineru_cloud_converter.py` | 仅该文件 |
| 3 | 更新单元测试中 `can_handle` 的断言 | 测试文件 | 测试覆盖 |
| 4 | 更新 `MinerUCloudConverter` 类 docstring | `mineru_cloud_converter.py` | 文档 |
