# 配置参考

本文列出文档处理模块所有配置项的完整参考，包括环境变量名、YAML 路径、默认值和说明。配置文件位于 `newbee_notebook/configs/document_processing.yaml`，所有值均支持 `${ENV_VAR:default}` 格式的环境变量注入。

## 1. 全局配置

| 环境变量 | YAML 路径 | 默认值 | 类型 | 说明 |
|----------|-----------|--------|------|------|
| `MINERU_ENABLED` | `document_processing.mineru_enabled` | `true` | bool | 全局启用/禁用 MinerU。`false` 时仅使用 MarkItDown |
| `MINERU_MODE` | `document_processing.mineru_mode` | `cloud` | string | `cloud`（云端）或 `local`（本地 Docker） |
| `DOCUMENTS_DIR` | `document_processing.documents_dir` | `data/documents` | string | Markdown 及资源文件的输出根目录 |

## 2. 云端模式配置（MINERU_MODE=cloud）

| 环境变量 | YAML 路径 | 默认值 | 类型 | 说明 |
|----------|-----------|--------|------|------|
| `MINERU_API_KEY` | `document_processing.mineru_cloud.api_key` | `""` | string | MinerU API 密钥（必填；为空时云端转换器静默禁用） |
| `MINERU_V4_API_BASE` | `document_processing.mineru_cloud.api_base` | `https://mineru.net` | string | API 基础 URL |
| `MINERU_V4_TIMEOUT` | `document_processing.mineru_cloud.timeout_seconds` | `120` | int | 单个 API 请求读取超时（秒） |
| `MINERU_V4_POLL_INTERVAL` | `document_processing.mineru_cloud.poll_interval` | `5` | int | 任务状态轮询间隔（秒） |
| `MINERU_V4_MAX_WAIT_SECONDS` | `document_processing.mineru_cloud.max_wait_seconds` | `1800` | int | 单个任务最长等待时间（秒，30 分钟） |
| `MINERU_CDN_CURL_FALLBACK_ENABLED` | `document_processing.mineru_cloud.cdn_curl_fallback_enabled` | `true` | bool | ZIP 下载 SSL 握手失败时，改用系统 `curl` 重试 |
| `MINERU_CDN_CURL_BINARY` | `document_processing.mineru_cloud.cdn_curl_binary` | `curl` | string | `curl` 可执行文件路径或名称 |
| `MINERU_CDN_CURL_INSECURE` | `document_processing.mineru_cloud.cdn_curl_insecure` | `false` | bool | curl 加 `-k` 跳过 SSL 验证（仅用于故障排查，生产不开启） |

## 3. 本地模式配置（MINERU_MODE=local）

| 环境变量 | YAML 路径 | 默认值 | 类型 | 说明 |
|----------|-----------|--------|------|------|
| `MINERU_LOCAL_API_URL` | `document_processing.mineru_local.api_url` | `http://mineru-api:8000` | string | 本地 Docker 服务地址 |
| `MINERU_BACKEND` | `document_processing.mineru_local.backend` | `pipeline` | string | 解析后端（`pipeline` / `vlm-auto-engine` / `hybrid-auto-engine` 等） |
| `MINERU_LANG_LIST` | `document_processing.mineru_local.lang_list` | `ch,en` | string | OCR 语言列表，逗号分隔 |
| `MINERU_LOCAL_TIMEOUT` | `document_processing.mineru_local.timeout_seconds` | `0` | int | 请求读取超时（秒）；`0` 表示无超时 |
| `MINERU_LOCAL_MAX_PAGES_PER_BATCH` | `document_processing.mineru_local.max_pages_per_batch` | `50` | int | 大 PDF 分批处理时每批最大页数；默认值下调以给 GPU/WSL2 留出更多波动余量 |
| `MINERU_LOCAL_REQUEST_RETRY_ATTEMPTS` | `document_processing.mineru_local.request_retry_attempts` | `2` | int | 本地 API 瞬时失败时的重试次数；总尝试次数 = 1 次首次请求 + 重试次数 |
| `MINERU_LOCAL_RETRY_BACKOFF_SECONDS` | `document_processing.mineru_local.retry_backoff_seconds` | `10` | float | 本地 API 重试的指数退避基数（秒） |
| `MINERU_LOCAL_RETURN_IMAGES` | `document_processing.mineru_local.return_images` | `true` | bool | 是否请求本地服务返回提取的图像 |
| `MINERU_LOCAL_RETURN_CONTENT_LIST` | `document_processing.mineru_local.return_content_list` | `true` | bool | 是否返回结构化内容列表（`content_list_v2.json`） |
| `MINERU_LOCAL_RETURN_MODEL_OUTPUT` | `document_processing.mineru_local.return_model_output` | `true` | bool | 是否返回模型原始输出（`*_model.json`） |

## 4. 断路器配置

断路器对 cloud 和 local 两种 MinerU 模式均生效，详见 [01-converter-architecture.md § 4](01-converter-architecture.md)。

| 环境变量 | YAML 路径 | 默认值 | 类型 | 说明 |
|----------|-----------|--------|------|------|
| `MINERU_FAIL_THRESHOLD` | `document_processing.fail_threshold` | `5` | int | 连续失败多少次后进入冷却期 |
| `MINERU_COOLDOWN_SECONDS` | `document_processing.cooldown_seconds` | `120` | float | 冷却期时长（秒）；期间跳过 MinerU，直接用 MarkItDown |

## 5. 配置示例

以下为 `.env` 文件中的典型配置片段：

**云端模式**

```dotenv
MINERU_ENABLED=true
MINERU_MODE=cloud
MINERU_API_KEY=eyJ0...（从 mineru.net 申请）
MINERU_V4_TIMEOUT=120
MINERU_V4_MAX_WAIT_SECONDS=1800
MINERU_FAIL_THRESHOLD=5
MINERU_COOLDOWN_SECONDS=120
```

**本地模式**

```dotenv
MINERU_ENABLED=true
MINERU_MODE=local
MINERU_LOCAL_API_URL=http://mineru-api:8000
MINERU_BACKEND=hybrid-auto-engine
MINERU_LANG_LIST=ch,en
MINERU_LOCAL_TIMEOUT=0
MINERU_LOCAL_MAX_PAGES_PER_BATCH=50
MINERU_LOCAL_REQUEST_RETRY_ATTEMPTS=2
MINERU_LOCAL_RETRY_BACKOFF_SECONDS=10
```

**仅使用 MarkItDown（禁用 MinerU）**

```dotenv
MINERU_ENABLED=false
```

## 6. 配置验证行为

| 情况 | 行为 |
|------|------|
| `MINERU_MODE=cloud` 且 `MINERU_API_KEY` 为空 | 云端转换器静默禁用，仅使用 MarkItDown，打印 warning 日志 |
| `MINERU_MODE` 为非法值 | MinerU 转换器静默禁用，仅使用 MarkItDown，打印 warning 日志 |
| `MINERU_FAIL_THRESHOLD` < 1 | 自动修正为 1 |
| `MINERU_COOLDOWN_SECONDS` < 1 | 自动修正为 1 |
| `MINERU_LOCAL_MAX_PAGES_PER_BATCH` < 1 | 自动修正为 1 |
| `MINERU_LOCAL_REQUEST_RETRY_ATTEMPTS` < 0 | 自动修正为 0 |
| `MINERU_LOCAL_RETRY_BACKOFF_SECONDS` < 0 | 自动修正为 0 |
| `MINERU_V4_POLL_INTERVAL` <= 0 | `MinerUCloudConverter.__init__` 抛出 `ValueError` |
