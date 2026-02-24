# 转换器链架构

本文描述 `DocumentProcessor` 的转换器链组装规则、各转换器的职责边界、fallback 调度机制以及断路器逻辑。配置项见 [04-config-reference.md](04-config-reference.md)。

## 1. 整体结构

文档处理的核心类是 `DocumentProcessor`（`processor.py`），它在初始化时按优先级组装一条转换器链，转换时依次尝试，第一个成功的结果直接返回。

```
用户上传文件
    |
    v
DocumentProcessor.convert(file_path)
    |
    +-- 按扩展名过滤出能处理该格式的 converters
    |
    +-- for each converter:
    |       断路器冷却中? -> skip
    |       try convert() -> 成功 -> return 结果
    |                     -> 失败 -> 记录错误, 继续下一个
    |
    +-- 所有 converter 均失败 -> RuntimeError（包含完整错误链）
```

## 2. 转换器链组装规则

`DocumentProcessor.__init__` 依据配置按顺序追加 converter：

```
MINERU_ENABLED=true 且 MINERU_MODE=cloud 且 MINERU_API_KEY 非空
    -> 追加 MinerUCloudConverter

MINERU_ENABLED=true 且 MINERU_MODE=local
    -> 追加 MinerULocalConverter

无条件追加 MarkItDownConverter（始终存在）
```

两种 MinerU 模式互斥，不会同时出现在同一条链中。`MINERU_API_KEY` 为空时，cloud 模式静默降级为仅用 MarkItDown，并打印 warning 日志。

## 3. 各转换器职责

### 3.1 MinerUCloudConverter

调用 MinerU v4 Smart Parsing 云端 API，完整流程见 [02-cloud-api.md](02-cloud-api.md)。

**当前支持格式**：仅 `.pdf`（`can_handle()` 硬编码）

**内部流程**：
```
申请预签名上传 URL (POST /api/v4/file-urls/batch)
    -> 上传文件 (PUT presigned URL)
    -> 轮询任务状态 (GET /api/v4/extract-results/batch/{batch_id})
    -> 下载结果 ZIP
    -> 解析 ZIP 提取 markdown、图像、元数据
```

**关键行为**：
- 所有网络调用通过 `asyncio.to_thread()` 在线程池中执行，不阻塞事件循环
- ZIP 下载失败时，自动 fallback 至系统 `curl`（可配置禁用）
- ZIP 解析优先使用 `full.md`，次选第一个 `.md` 文件
- `image_assets` 包含 ZIP 内 `images/` 目录下的所有图像字节
- `metadata_assets` 包含所有 `.json` 文件（`content_list_v2.json`、`layout.json` 等）
- 页数从 `layout.json` 的 `pdf_info[].length` 中提取；提取失败时调用 `PdfReader` 计数

**触发 fallback 的异常类型**：
- `requests.RequestException`（网络层故障）
- `TimeoutError`
- `MinerUCloudTransientError`（ZIP 下载全部方式均失败时抛出）

### 3.2 MinerULocalConverter

调用本地 Docker 中运行的 MinerU FastAPI 服务（`POST /file_parse`）。

**当前支持格式**：仅 `.pdf`

**分批处理**：当 PDF 页数超过 `max_pages_per_batch`（默认 60）时自动分批，每批之间执行 `gc.collect()` 控制内存峰值。分批结果的 markdown 换行拼接，image/metadata assets 加前缀 `batch{N}/` 合并。

**触发 fallback 的异常类型**：
- `requests.RequestException`
- `TimeoutError`

### 3.3 MarkItDownConverter

调用 Python `markitdown` 库，同步操作通过 `asyncio.to_thread()` 在线程池中执行。

**支持格式**：`.pdf`、`.docx`、`.doc`、`.xlsx`、`.xls`、`.pptx`、`.csv`、`.txt`、`.md`、`.markdown`、`.html`、`.htm`

**特点**：
- 不返回图像资源（`image_assets=None`）
- 不返回元数据（`metadata_assets=None`）
- `page_count` 固定为 `1`
- PDF 处理依赖 `pdfminer.six`，缺失时在运行时抛出 `RuntimeError`

## 4. 断路器

断路器作用于 MinerU 转换器（cloud 和 local），防止持续故障拖慢每个请求。

**状态变量**（`DocumentProcessor` 实例级别）：

| 变量 | 含义 |
|------|------|
| `_mineru_consecutive_failures` | 当前连续失败计数 |
| `_mineru_unavailable_until` | 冷却期结束时刻（`time.monotonic()`） |

**触发逻辑**：

```
每次 MinerU 转换失败（符合触发条件的异常）:
    _mineru_consecutive_failures += 1

    if _mineru_consecutive_failures >= fail_threshold (默认 5):
        _mineru_unavailable_until = now + cooldown_seconds (默认 120s)
        _mineru_consecutive_failures = 0  # 重置，开始下一轮计数
```

**冷却期行为**：在冷却期内，所有请求直接跳过 MinerU，由 MarkItDown 处理，不记录额外失败。

**恢复**：任意一次 MinerU 转换成功即重置 `_mineru_consecutive_failures = 0`，断路器回到正常状态。

**注意**：断路器状态保存在 `DocumentProcessor` 实例中，Celery worker 多进程部署时各进程独立计数。

## 5. 格式路由示例

以 `document.docx` 为例（backend-v2 扩展后）：

```
cloud 模式:
    converter 链: [MinerUCloudConverter, MarkItDownConverter]

    MinerUCloudConverter.can_handle(".docx") -> True (扩展后)
    尝试云端解析 -> 成功 -> 返回结果，含图像和元数据
                -> 失败 -> 触发 fallback

    MarkItDownConverter.can_handle(".docx") -> True
    MarkItDown 解析 -> 成功 -> 返回结果（无图像）

local 模式:
    converter 链: [MinerULocalConverter, MarkItDownConverter]

    MinerULocalConverter.can_handle(".docx") -> False
    跳过 MinerULocalConverter

    MarkItDownConverter.can_handle(".docx") -> True
    MarkItDown 解析 -> 返回结果
```
