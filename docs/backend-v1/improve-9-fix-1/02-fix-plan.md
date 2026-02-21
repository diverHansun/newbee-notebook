# 02 - 修复方案：批间内存释放与配置优化

## 1. 修复思路

### 1.1 原则

- 不修改 MinerU 第三方包的源码或启动入口。
- 优先使用 MinerU 预留的环境变量接口修正配置行为。
- 清理逻辑放在后端 Converter 和 Admin API 中，保持 MinerU 容器的独立性。
- 删除前次迭代中错误的 wrapper 脚本注入方案。

### 1.2 修复分层

| 层级 | 修复手段 | 作用 |
|------|----------|------|
| MinerU 容器（配置） | 设置 `MINERU_VIRTUAL_VRAM_SIZE=8` | 绕过阈值，使 `clean_vram()` 在每个推理阶段后正常触发 |
| 后端 Converter | 批循环中 `del result` + `gc.collect()` | 释放本地的 ZIP 解压数据、Markdown、图像字节 |
| 后端 Converter | 默认开启 `return_content_list` / `return_model_output`（可配置关闭） | 保留结构化元数据，支撑前端图片定位与问题排查 |
| 后端 Converter | 批大小从 20 提升至 60 | 减少批次数，降低请求开销 |
| Celery Worker | 显式设置并发/预取/子进程重生参数 | 降低多任务叠加与长期运行内存碎片 |
| 后端 Admin API | 新增 `POST /admin/system/cleanup` | 手动触发后端进程 GC，运维可操作 |
| 后端 Admin API | 新增 `GET /admin/system/memory` | 查询后端进程和 MinerU 容器的内存状态 |
| 部署文件 | 删除 `mineru_wrapper.py`，恢复 Dockerfile.gpu | 移除错误的 wrapper 注入方案 |
| 前端 Viewer | 分段渐进渲染 + 图片加载状态优化 + 路径兜底 | 解决长文档滚动卡顿、提升图片显示稳定性 |

## 2. MinerU 容器：环境变量修正

### 2.1 `MINERU_VIRTUAL_VRAM_SIZE` 的作用

MinerU 的 `get_vram(device)` 函数优先读取 `MINERU_VIRTUAL_VRAM_SIZE` 环境变量，返回值用于两个场景：

1. `clean_vram()` 的阈值判断：`if total_memory <= 8: clean_memory(device)`
2. 推理批大小计算：`batch_ratio = total_memory / 8`

设置 `MINERU_VIRTUAL_VRAM_SIZE=8` 后：

- `clean_vram()` 判断 `8 <= 8`，为 `True`，清理逻辑被激活。
- `batch_ratio = 8 / 8 = 1`，推理批大小使用默认基准值（不激进放大），与 8 GB 显存设备的行为一致。

这不会降低推理精度或功能，仅使 MinerU 在处理完每个推理阶段后执行：

```python
def clean_memory(device='cuda'):
    torch.cuda.empty_cache()
    torch.cuda.ipc_collect()
    gc.collect()
```

### 2.2 配置变更

在 `docker-compose.gpu.yml` 的 `mineru-api` 服务中增加环境变量：

```yaml
environment:
  MINERU_VIRTUAL_VRAM_SIZE: "8"
```

这是唯一需要的容器侧修改。不需要修改 Dockerfile、不需要注入脚本、不需要修改 CMD。

## 3. 后端 Converter：批间清理

### 3.1 修改位置

`newbee_notebook/infrastructure/document_processing/converters/mineru_local_converter.py`

### 3.2 批循环的改进

在每个批次处理完成后、下一个批次开始前，执行以下清理：

```python
for batch_start in range(0, total_pages, self._max_pages_per_batch):
    result = await self._convert_range(...)

    # 提取需要的数据到合并容器
    all_markdown.append(result.markdown)
    # ... 合并 image_assets, metadata_assets ...

    # 清理：显式释放批次结果引用
    del result

    # 清理：触发 Python GC 回收批次数据
    if batch_num < num_batches:
        gc.collect()
```

### 3.3 批大小调整

默认批大小从 20 页提升至 60 页：

| 参数 | 旧值 | 新值 | 依据 |
|------|------|------|------|
| `_DEFAULT_MAX_PAGES_PER_BATCH` | 20 | 60 | 60 页 x 10.7 MB = 640 MB，加模型约 4 GB，远低于 16 GB |
| `processor.py` 默认值 | 20 | 60 | 与 Converter 常量保持一致 |

462 页 PDF 处理批次数从 24 批降至 8 批，减少约 67% 的 HTTP 请求开销。

### 3.4 返回载荷策略（更新）

本地转换默认保留主链路 + 结构化元数据：

- `return_md=true`
- `return_images=true`
- `return_content_list=true`（默认开启）
- `return_model_output=true`（默认开启）

`content_list/model_output` 可用于：

- 前端图片位置兜底（当 markdown 图片标记异常时可恢复）
- 文档解析问题复盘（定位具体页、块、bbox）
- 后续结构化增强（表格/图像后处理）

如果出现极端内存压力，可通过环境变量临时关闭：

- `MINERU_LOCAL_RETURN_CONTENT_LIST=false`
- `MINERU_LOCAL_RETURN_MODEL_OUTPUT=false`

### 3.5 流式下载 ZIP（新增）

Converter 从“整包 bytes 一次性读入”改为“流式写临时 ZIP 文件再解析”，减少单次请求中的峰值字节驻留时间。

## 4. Celery Worker：并发与生命周期控制（新增）

### 4.1 建议参数

在 worker 启动命令中显式设置：

- `--concurrency=${CELERY_CONCURRENCY:-1}`
- `--prefetch-multiplier=${CELERY_PREFETCH_MULTIPLIER:-1}`
- `--max-tasks-per-child=${CELERY_MAX_TASKS_PER_CHILD:-4}`

含义：

- 并发控制同机可同时处理的文档任务数；
- prefetch=1 防止某个 worker 提前抓取太多任务；
- 子进程周期重建，缓解长跑进程内存碎片累积。

### 4.2 任务后清理（新增）

文档任务结束后执行：

- `gc.collect()`
- 可选 `torch.cuda.empty_cache()`（由环境变量控制）

用于降低进程级内存驻留惯性。

## 5. 后端 Admin API：系统清理与诊断

### 4.1 新增端点

在 `newbee_notebook/api/routers/admin.py` 中新增两个端点：

#### `POST /api/v1/admin/system/cleanup`

手动触发后端进程的 Python GC。用于运维在处理大量文档后主动释放进程内存。

请求：无参数。

响应：

```json
{
  "status": "ok",
  "gc_collected": 1523,
  "rss_before_mb": 456.2,
  "rss_after_mb": 412.8
}
```

#### `GET /api/v1/admin/system/memory`

查询后端进程的内存使用情况，以及 MinerU 容器的健康状态。

响应：

```json
{
  "backend": {
    "rss_mb": 412.8,
    "vms_mb": 1024.5
  },
  "mineru": {
    "status": "healthy",
    "docs_url": "http://mineru-api:8000/docs"
  }
}
```

### 4.2 设计约束

- 清理端点仅影响后端 FastAPI 进程本身，不操作 MinerU 容器（MinerU 的清理由 `MINERU_VIRTUAL_VRAM_SIZE` 环境变量自动保证）。
- 诊断端点不暴露敏感信息，仅返回内存占用数值和服务状态。
- 两个端点均在 Admin 路由组下，复用现有的路由前缀 `/admin`。

## 6. 部署文件：清理错误方案

### 5.1 删除文件

- `docker/mineru/mineru_wrapper.py`：错误的 wrapper 注入脚本，应删除。

### 5.2 恢复 Dockerfile.gpu

将 CMD 恢复为官方的 `mineru-api` CLI 入口，移除 wrapper 的 COPY 和 CMD 修改：

```dockerfile
# 恢复前（错误）
COPY mineru_wrapper.py /app/mineru_wrapper.py
CMD ["python", "/app/mineru_wrapper.py"]

# 恢复后（正确）
CMD ["mineru-api", "--host", "0.0.0.0", "--port", "8000"]
```

## 7. 代码变更清单

| 序号 | 文件 | 操作 | 说明 |
|------|------|------|------|
| 1 | `docker/mineru/mineru_wrapper.py` | 删除 | 移除错误的 wrapper 脚本 |
| 2 | `docker/mineru/Dockerfile.gpu` | 修改 | 删除 COPY wrapper，恢复 CMD 为 `mineru-api` |
| 3 | `docker-compose.gpu.yml` | 修改 | 新增 `MINERU_VIRTUAL_VRAM_SIZE: "8"` |
| 4 | `mineru_local_converter.py` | 修改 | 批循环增加 `del result` + `gc.collect()`，批大小 20 改 60，移除 `_cleanup_remote()` |
| 5 | `processor.py` | 修改 | 默认 `max_pages_per_batch` 20 改 60 |
| 6 | `admin.py` | 修改 | 新增 `POST /admin/system/cleanup`、`GET /admin/system/memory` |
| 7 | `document_processing.yaml` | 修改 | 增加本地 converter 的批大小与返回载荷开关 |
| 8 | `docker-compose*.yml` | 修改 | worker 显式并发参数；GPU MinerU 并发默认收敛到 1 |
| 9 | `document_tasks.py` | 修改 | 任务结束后 worker 进程内存清理 |
| 10 | `postman_collection.json` | 修改 | 新增 `System Memory`、`System Cleanup` 请求 |
| 11 | `document_processing.yaml` | 修改 | `return_content_list/model_output` 默认改为开启 |
| 12 | `processor.py` | 修改 | 本地 converter 默认元数据开关改为 `True` |
| 13 | `mineru_local_converter.py` | 修改 | 构造函数默认元数据开关改为 `True` |
| 14 | `.env.example` | 修改 | 示例环境变量默认值与说明同步更新 |
| 15 | `markdown-pipeline.ts` | 修改 | 图片路径规范化、按内容启用插件、图片加载状态标记 |
| 16 | `markdown-viewer.tsx` | 修改 | 大文档分段渐进渲染（IntersectionObserver） |
| 17 | `markdown-content.css` | 修改 | 图片动画仅未加载时生效；新增 chunk/load-more 样式 |
| 18 | `document-reader.tsx` | 修改 | 透传 `documentId` 给 markdown 渲染管线 |
| 19 | `test_document_processing_processor.py` | 修改 | 新增默认开启元数据与可关闭的单测 |

## 8. 内存预算验证

以 462 页 PDF、60 页/批为例：

| 组件 | 内存占用 |
|------|----------|
| MinerU 模型权重 | 约 4 GB（常驻，跨批次共享） |
| 单批页面图像（PIL + NumPy） | 约 1.28 GB（60 x 10.7 MB x 2） |
| MinerU 推理中间数据 | 约 0.5 GB |
| Python/OS/Docker 开销 | 约 2 GB |
| 合计 | 约 7.78 GB |
| WSL2 可用内存 | 16 GB |
| 安全余量 | 约 8.2 GB (53%) |

配合 `MINERU_VIRTUAL_VRAM_SIZE=8` 使清理在推理阶段间自动触发，和 Converter 侧的 `gc.collect()` 在批次间释放本地数据，内存使用将保持在安全范围内。

## 9. 运行态验证清单（新增）

部署后请逐项确认：

1. `docker inspect newbee-notebook-mineru-api` 中包含 `MINERU_VIRTUAL_VRAM_SIZE=8`。
2. `docker logs newbee-notebook-celery-worker` 显示 `concurrency` 为期望值（建议 1）。
3. 大 PDF 日志中出现 `processing in batches of 60` 与批间 `local gc completed`。
4. `POST /api/v1/admin/system/cleanup` 可返回 `status=ok`。
5. `GET /api/v1/admin/system/memory` 可返回 backend/mineru 状态字段。

## 10. 前端 Viewer 优化（新增）

### 10.1 发现的问题

- `View` 页面一次性同步渲染整篇 markdown（超长文档时会阻塞主线程）。
- 图片 shimmer 动画对所有 lazy image 持续生效，导致大量图片时持续重绘。
- 部分文档图片路径可能是 `images/...`，前端缺少统一转换逻辑。

### 10.2 修复内容

- markdown 渲染改为“分段渐进加载”，首屏只渲染部分 chunk，滚动触发后续 chunk。
- 图片样式改为仅在 `data-loaded="0"` 时显示占位动画，加载完成后停止动画。
- 渲染管线新增图片 URL 规范化：支持将 `images/...`、`assets/images/...` 自动映射到 `/api/v1/documents/{id}/assets/images/...`。

### 10.3 验证方式

1. 打开大文档 `View`，确认首屏可立即滚动。
2. 向下滚动，观察“正在加载更多内容...”提示按需出现并继续渲染。
3. 检查 markdown 中的图片在对应位置正常展示，404 时显示 fallback 提示。
