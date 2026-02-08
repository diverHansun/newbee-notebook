# 架构设计

## 1. 整体架构

### 1.1 MinerU 服务对比

| 对比项 | 云服务（mineru.net） | 本地服务（Docker） |
|--------|---------------------|-------------------|
| 部署方式 | SaaS，无需部署 | Docker 容器 |
| 认证方式 | Pipeline ID | 无（内网） |
| API 协议 | RESTful（异步） | RESTful（同步） |
| 工作模式 | 上传 -> 轮询结果 | 直接返回结果 |
| 处理速度 | 快（云端 GPU） | 慢（本地 CPU）或快（本地 GPU） |
| 资源占用 | 无本地占用 | 容器常驻内存 |
| 使用限制 | 10 文件/pipeline，100MB，10 页 | 无限制 |
| 网络要求 | 需要外网 | 无需外网 |

### 1.2 架构演进

```
当前架构：
┌──────────────┐
│ FastAPI      │
└──────┬───────┘
       │
       ▼
┌──────────────────┐      ┌──────────────────┐
│ DocumentProcessor│─────▶│ MinerUConverter  │
└──────────────────┘      └────────┬─────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │ MinerU Docker   │
                          │  (本地强依赖)    │
                          └─────────────────┘

新架构：
┌──────────────┐
│ FastAPI      │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────┐
│     DocumentProcessor            │
│   (根据 MINERU_MODE 选择)         │
└────────┬─────────────────────────┘
         │
         ├─ mode=cloud ──────────────────────┐
         │                                   │
         │                                   ▼
         │                      ┌───────────────────────┐
         │                      │ MinerUCloudConverter  │
         │                      │   (mineru-kie-sdk)    │
         │                      └──────────┬────────────┘
         │                                 │
         │                                 ▼
         │                      ┌───────────────────────┐
         │                      │  mineru.net API       │
         │                      │  (云服务，无需部署)    │
         │                      └───────────────────────┘
         │
         └─ mode=local ──────────────────────┐
                                             │
                                             ▼
                                ┌───────────────────────┐
                                │ MinerULocalConverter  │
                                │   (原实现保持)         │
                                └──────────┬────────────┘
                                           │
                                           ▼
                                ┌───────────────────────┐
                                │ MinerU Docker         │
                                │ (CPU/GPU 可选)        │
                                └───────────────────────┘

Fallback 机制（所有模式共享）：
         MinerU (任意模式) ──失败──▶ PyPDF ──失败──▶ MarkItDown
```

## 2. 三模式详细设计

### 2.1 Cloud 模式

#### 认证机制

```
Pipeline ID 获取流程：
1. 访问 mineru.net
2. 创建 Pipeline（配置处理流程）
3. 部署 Pipeline
4. 获取 Pipeline ID（UUID 格式）
5. 配置到环境变量 MINERU_PIPELINE_ID
```

#### API 端点

```
基础 URL: https://mineru.net/api/kie

上传文件:
  POST /restful/pipelines/{pipeline_id}/upload
  - 字段名: files (multipart/form-data)
  - 响应: {"code": "succ", "data": {"files": [{"file_id": 123}]}}

查询结果:
  GET /restful/pipelines/{pipeline_id}/result
  - 响应: {
      "code": "succ",
      "data": {
        "file_status": [{
          "file_id": 123,
          "code": 0,  // 0=完成, 1=处理中, -1=失败, -2=等待
          "parse_result": {"md_content": "..."},
          "split_result": {...},
          "extract_result": {...}
        }]
      }
    }
```

#### 异步处理流程

```
┌─────────────┐
│ 上传文件     │
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│ 获取 file_id     │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ 开始轮询         │
│ (interval=5s)    │
└──────┬───────────┘
       │
       ├────────────────────────┐
       │                        │
       ▼                        │
┌──────────────────┐            │
│ 检查状态         │            │
└──────┬───────────┘            │
       │                        │
       ├─ code=1 (处理中) ──────┘
       │
       ├─ code=0 (完成) ───────┐
       │                       │
       │                       ▼
       │              ┌─────────────────┐
       │              │ 提取 md_content │
       │              └─────────────────┘
       │
       └─ code=-1 (失败) ──────┐
                               │
                               ▼
                      ┌─────────────────┐
                      │ 抛出异常，降级   │
                      └─────────────────┘
```

### 2.2 Local 模式

#### 同步处理流程

```
┌──────────────────┐
│ 调用 /file_parse │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ 阻塞等待处理     │
│ (timeout 可配)   │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ 直接返回结果     │
│ {md_content: ...}│
└──────────────────┘
```

#### CPU vs GPU 差异

| 配置项 | CPU 模式 | GPU 模式 |
|--------|----------|----------|
| Docker 镜像 | python:3.11-slim | vllm/vllm-openai:v0.11.0 |
| Backend | pipeline | hybrid-auto-engine |
| 并发限制 | 1 | 2 |
| 处理速度 | 慢 | 快 |
| GPU 要求 | 无 | NVIDIA GPU + cuda |

## 3. Converter 架构重构

### 3.1 类设计

```python
# 基类（保持不变）
class Converter(Protocol):
    def can_handle(self, ext: str) -> bool: ...
    async def convert(self, file_path: str) -> ConversionResult: ...

# 云服务 Converter（新增）
class MinerUCloudConverter(Converter):
    def __init__(self, pipeline_id: str, timeout: int = 300):
        from mineru_kie_sdk import MineruKIEClient
        self.client = MineruKIEClient(
            pipeline_id=pipeline_id,
            base_url="https://mineru.net/api/kie",
            timeout=30
        )
        self.processing_timeout = timeout

    async def convert(self, file_path: str) -> ConversionResult:
        # 1. 上传前检查限制
        # 2. 调用 SDK 上传
        # 3. 轮询获取结果
        # 4. 提取 markdown

# 本地服务 Converter（重命名，逻辑不变）
class MinerULocalConverter(Converter):
    def __init__(self, base_url: str, timeout: int, backend: str, lang_list: str):
        # 保持原有实现

# 其他 Converter（保持不变）
class PyPdfConverter(Converter): ...
class MarkItDownConverter(Converter): ...
```

### 3.2 DocumentProcessor 初始化

```python
class DocumentProcessor:
    def __init__(self, config: Optional[dict] = None):
        cfg = config or get_document_processing_config()
        dp_cfg = cfg.get("document_processing", {})

        mode = dp_cfg.get("mineru_mode", "cloud")
        converters = []

        # 根据模式初始化 Converter
        if mode == "cloud":
            pipeline_id = dp_cfg.get("mineru_cloud", {}).get("pipeline_id")
            if pipeline_id:
                converters.append(MinerUCloudConverter(
                    pipeline_id=pipeline_id,
                    timeout=dp_cfg.get("mineru_cloud", {}).get("timeout_seconds", 300)
                ))
            else:
                logger.warning("Cloud mode enabled but no pipeline_id provided")

        elif mode == "local":
            local_cfg = dp_cfg.get("mineru_local", {})
            converters.append(MinerULocalConverter(
                base_url=local_cfg.get("api_url", "http://mineru-api:8000"),
                timeout=local_cfg.get("timeout_seconds", 0),
                backend=local_cfg.get("backend", "pipeline"),
                lang_list=local_cfg.get("lang_list", "ch")
            ))

        # Fallback converters（所有模式都加）
        converters.extend([PyPdfConverter(), MarkItDownConverter()])
        self._converters = converters
```

### 3.3 Fallback 机制

```
文档转换流程：
┌─────────────────────────┐
│ 选择 Converters         │
│ [MinerU, PyPDF, MarkIt] │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 尝试 MinerU             │◀─────┐
└───────────┬─────────────┘      │
            │                    │
            ├─ 成功 ─────────────┼──▶ 返回结果
            │                    │
            ├─ 网络错误 ─────────┤
            │   (云服务不可达)     │
            │   记录错误，继续     │
            │                    │
            ├─ 限制错误 ─────────┤
            │   (文件过大/页数)    │
            │   记录错误，继续     │
            │                    │
            ▼                    │
┌─────────────────────────┐      │
│ 尝试 PyPDF              │      │
└───────────┬─────────────┘      │
            │                    │
            ├─ 成功 ─────────────┼──▶ 返回结果
            │                    │
            ├─ 失败 ─────────────┤
            │                    │
            ▼                    │
┌─────────────────────────┐      │
│ 尝试 MarkItDown         │      │
└───────────┬─────────────┘      │
            │                    │
            ├─ 成功 ─────────────┼──▶ 返回结果
            │                    │
            └─ 失败 ─────────────┴──▶ 抛出异常
```

## 4. 配置架构

### 4.1 配置文件结构

```yaml
document_processing:
  # 全局开关
  mineru_enabled: ${MINERU_ENABLED:true}

  # 模式选择: cloud | local
  mineru_mode: ${MINERU_MODE:cloud}

  # 云服务配置
  mineru_cloud:
    pipeline_id: ${MINERU_PIPELINE_ID:}
    base_url: ${MINERU_CLOUD_BASE_URL:https://mineru.net/api/kie}
    timeout_seconds: ${MINERU_CLOUD_TIMEOUT:300}
    poll_interval: ${MINERU_CLOUD_POLL_INTERVAL:5}

  # 本地服务配置
  mineru_local:
    api_url: ${MINERU_LOCAL_API_URL:http://mineru-api:8000}
    backend: ${MINERU_BACKEND:pipeline}
    lang_list: ${MINERU_LANG_LIST:ch}
    timeout_seconds: ${MINERU_LOCAL_TIMEOUT:0}

  # 通用配置
  unavailable_cooldown_seconds: 300
  documents_dir: ${DOCUMENTS_DIR:data/documents}
```

### 4.2 环境变量优先级

```
配置加载顺序（优先级从高到低）：
1. 环境变量（export MINERU_MODE=cloud）
2. .env 文件
3. YAML 文件中的默认值
```

## 5. Docker 架构调整

### 5.1 依赖关系变更

**原依赖关系**：
```
celery-worker ──强依赖──▶ mineru-api
```

**新依赖关系**：
```
celery-worker ──条件依赖──▶ mineru-api (仅 mode=local 且 profile=mineru-local)
```

### 5.2 启动场景对比

| 场景 | 命令 | 启动的服务 |
|------|------|-----------|
| 默认（云服务） | `docker-compose up -d` | postgres, redis, es, celery-worker |
| 本地 CPU | `docker-compose --profile mineru-local up -d` | 上述 + mineru-api (CPU) |
| 本地 GPU | `docker-compose -f docker-compose.yml -f docker-compose.gpu.yml --profile mineru-local up -d` | 上述 + mineru-api (GPU) |

## 6. 错误处理

### 6.1 云服务限制处理

```python
# 上传前检查
async def convert(self, file_path: str) -> ConversionResult:
    path = Path(file_path)

    # 检查文件大小
    size = path.stat().st_size
    if size > 100 * 1024 * 1024:
        raise ValueError(
            f"文件过大 ({size / 1024 / 1024:.1f}MB)，"
            f"云服务限制为 100MB，将使用本地处理"
        )

    # 检查页数（仅 PDF）
    if path.suffix.lower() == ".pdf":
        page_count = await self._count_pages(path)
        if page_count > 10:
            raise ValueError(
                f"PDF 页数过多 ({page_count} 页)，"
                f"云服务限制为 10 页，将使用本地处理"
            )

    # 执行上传和处理
    ...
```

### 6.2 错误类型及处理策略

| 错误类型 | 示例 | 处理策略 |
|----------|------|----------|
| 认证错误 | Pipeline ID 无效 | 记录错误，降级到 PyPDF |
| 网络错误 | 连接超时 | 启用 cooldown（5min），降级到 PyPDF |
| 限制错误 | 文件过大、页数超限 | 记录警告，降级到 PyPDF |
| Pipeline 满 | 10 文件上限 | 记录错误，提示创建新 Pipeline |
| 处理失败 | code=-1 | 记录错误，降级到 PyPDF |
| 超时 | 轮询超时 | 记录警告，降级到 PyPDF |

### 6.3 Circuit Breaker 机制

```python
# DocumentProcessor 中的熔断机制
class DocumentProcessor:
    def __init__(self, ...):
        self._mineru_unavailable_until: float = 0.0
        self._mineru_unavailable_cooldown = 300  # 5 分钟

    async def convert(self, file_path: str) -> ConversionResult:
        for converter in self._converters:
            # 如果是 MinerU 且在熔断期，跳过
            if isinstance(converter, MinerUCloudConverter):
                if time.monotonic() < self._mineru_unavailable_until:
                    logger.info("MinerU 云服务在熔断期，跳过")
                    continue

            try:
                return await converter.convert(file_path)
            except Exception as e:
                # 网络错误触发熔断
                if isinstance(converter, MinerUCloudConverter):
                    if isinstance(e, (httpx.ConnectError, httpx.TimeoutError)):
                        self._mineru_unavailable_until = (
                            time.monotonic() + self._mineru_unavailable_cooldown
                        )
                        logger.warning(
                            f"MinerU 云服务不可达，熔断 {self._mineru_unavailable_cooldown}s"
                        )

                # 继续尝试下一个 converter
                continue
```

## 7. 并发与状态管理

### 7.1 Pipeline 文件限制

云服务限制每个 Pipeline 最多 10 个文件，需要在应用层管理：

```python
# 建议：定期清理或使用多个 Pipeline 轮换
# 1. 在 mineru.net 创建多个 Pipeline
# 2. 配置多个 Pipeline ID（轮询使用）
# 3. 或定期手动清理旧文件
```

### 7.2 重复上传处理

```python
# SDK 内部无去重，应用层控制
# 建议：处理前检查文档状态，避免重复提交
async def process_document_task(document_id: str):
    document = await get_document(document_id)

    if document.status in [DocumentStatus.PROCESSING, DocumentStatus.COMPLETED]:
        logger.info(f"文档 {document_id} 已处理，跳过")
        return

    # 执行处理
    ...
```

## 8. 性能优化

### 8.1 超时配置建议

| 参数 | Cloud 建议值 | Local CPU 建议值 | Local GPU 建议值 |
|------|-------------|-----------------|-----------------|
| timeout_seconds | 300 (5min) | 0 (无限) | 120 (2min) |
| poll_interval | 5s | N/A | N/A |

### 8.2 并发控制

```
云服务:
  - 无本地并发限制
  - 受 Pipeline 并发能力限制（由云端控制）

本地 CPU:
  - MINERU_API_MAX_CONCURRENT_REQUESTS=1（避免 CPU 过载）

本地 GPU:
  - MINERU_API_MAX_CONCURRENT_REQUESTS=2（根据显存调整）
```
