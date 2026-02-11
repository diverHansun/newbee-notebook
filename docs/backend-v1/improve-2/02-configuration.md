# 配置说明

## 1. 配置文件概览

### 1.1 配置文件层级

```
项目配置层级：
.env.example                    # 环境变量模板（新增字段）
.env                            # 实际环境变量（用户配置）
newbee_notebook/configs/
  └── document_processing.yaml  # 文档处理配置（修改）
```

### 1.2 配置优先级

```
环境变量 > .env 文件 > YAML 默认值
```

## 2. document_processing.yaml 配置

### 2.1 完整配置示例

```yaml
document_processing:
  # ==================== 全局配置 ====================
  # MinerU 总开关，设为 false 将只使用 PyPDF 和 MarkItDown
  mineru_enabled: ${MINERU_ENABLED:true}

  # 部署模式选择: cloud | local
  mineru_mode: ${MINERU_MODE:cloud}

  # ==================== 云服务配置 ====================
  mineru_cloud:
    # Pipeline ID（必填，在 mineru.net 创建）
    pipeline_id: ${MINERU_PIPELINE_ID:}

    # 云服务 API 基础 URL（通常不需要修改）
    base_url: ${MINERU_CLOUD_BASE_URL:https://mineru.net/api/kie}

    # 处理超时时间（秒），0 表示无限等待
    timeout_seconds: ${MINERU_CLOUD_TIMEOUT:300}

    # 轮询间隔（秒），建议 5-10 秒
    poll_interval: ${MINERU_CLOUD_POLL_INTERVAL:5}

  # ==================== 本地服务配置 ====================
  mineru_local:
    # 本地 MinerU API 地址
    api_url: ${MINERU_LOCAL_API_URL:http://mineru-api:8000}

    # 处理后端: pipeline (CPU) | hybrid-auto-engine (GPU)
    backend: ${MINERU_BACKEND:pipeline}

    # OCR 语言列表，逗号分隔
    lang_list: ${MINERU_LANG_LIST:ch,en}

    # 处理超时时间（秒），0 表示无限等待
    timeout_seconds: ${MINERU_LOCAL_TIMEOUT:0}

  # ==================== 通用配置 ====================
  # MinerU 不可用时的冷却时间（秒）
  unavailable_cooldown_seconds: 300

  # 文档存储根目录
  documents_dir: ${DOCUMENTS_DIR:data/documents}
```

### 2.2 配置字段说明

| 字段路径 | 类型 | 必填 | 说明 | 默认值 |
|----------|------|------|------|--------|
| `mineru_enabled` | bool | 否 | MinerU 总开关 | true |
| `mineru_mode` | string | 否 | 部署模式（cloud/local） | cloud |
| `mineru_cloud.pipeline_id` | string | 是* | Pipeline ID（cloud 模式必填） | 空 |
| `mineru_cloud.base_url` | string | 否 | 云服务 API 地址 | https://mineru.net/api/kie |
| `mineru_cloud.timeout_seconds` | int | 否 | 处理超时（秒） | 300 |
| `mineru_cloud.poll_interval` | int | 否 | 轮询间隔（秒） | 5 |
| `mineru_local.api_url` | string | 否 | 本地 API 地址 | http://mineru-api:8000 |
| `mineru_local.backend` | string | 否 | 处理后端 | pipeline |
| `mineru_local.lang_list` | string | 否 | OCR 语言 | ch,en |
| `mineru_local.timeout_seconds` | int | 否 | 处理超时（秒） | 0 |
| `unavailable_cooldown_seconds` | int | 否 | 熔断冷却时间 | 300 |
| `documents_dir` | string | 否 | 文档存储目录 | data/documents |

注：`*` 表示在特定模式下必填

## 3. 环境变量配置

### 3.1 .env.example 模板

```bash
# ========================================
# MinerU 文档处理配置
# ========================================

# 部署模式: cloud（云服务）| local（本地服务）
# 默认: cloud
MINERU_MODE=cloud

# ========================================
# 云服务配置（MINERU_MODE=cloud 时使用）
# ========================================

# Pipeline ID（必填）
# 获取方式：访问 https://mineru.net -> 创建 Pipeline -> 部署 -> 复制 ID
MINERU_PIPELINE_ID=

# 云服务 API 地址（通常不需要修改）
# MINERU_CLOUD_BASE_URL=https://mineru.net/api/kie

# 处理超时时间（秒），0 表示无限等待
# 建议值：300（5 分钟）
# MINERU_CLOUD_TIMEOUT=300

# 轮询间隔（秒）
# 建议值：5-10 秒
# MINERU_CLOUD_POLL_INTERVAL=5

# ========================================
# 本地服务配置（MINERU_MODE=local 时使用）
# ========================================

# 本地 MinerU API 地址
# Docker 内网地址，通常不需要修改
# MINERU_LOCAL_API_URL=http://mineru-api:8000

# 处理后端
# CPU 模式: pipeline
# GPU 模式: hybrid-auto-engine
# MINERU_BACKEND=pipeline

# OCR 语言列表（逗号分隔）
# 支持: ch, en, japan, korean 等
# MINERU_LANG_LIST=ch,en

# 处理超时时间（秒），0 表示无限等待
# CPU 模式建议 0（大文件可能需要很长时间）
# GPU 模式建议 120
# MINERU_LOCAL_TIMEOUT=0

# ========================================
# 通用配置
# ========================================

# MinerU 总开关
# MINERU_ENABLED=true

# 文档存储根目录
# DOCUMENTS_DIR=data/documents
```

### 3.2 实际配置示例

**场景 1：使用云服务**

```bash
# .env
MINERU_MODE=cloud
MINERU_PIPELINE_ID=550e8400-e29b-41d4-a716-446655440000
```

**场景 2：本地 CPU 模式**

```bash
# .env
MINERU_MODE=local
MINERU_BACKEND=pipeline
MINERU_LOCAL_TIMEOUT=0
```

**场景 3：本地 GPU 模式**

```bash
# .env
MINERU_MODE=local
MINERU_BACKEND=hybrid-auto-engine
MINERU_LOCAL_TIMEOUT=120
```

## 4. 模式切换

### 4.1 运行时切换

**从本地切换到云服务**：

```bash
# 1. 停止服务
docker-compose down

# 2. 修改 .env
sed -i 's/MINERU_MODE=local/MINERU_MODE=cloud/' .env
echo "MINERU_PIPELINE_ID=your-pipeline-id" >> .env

# 3. 重启服务（不包含 mineru-api 容器）
docker-compose up -d
```

**从云服务切换到本地**：

```bash
# 1. 停止服务
docker-compose down

# 2. 修改 .env
sed -i 's/MINERU_MODE=cloud/MINERU_MODE=local/' .env

# 3. 重启服务（包含 mineru-api 容器）
docker-compose --profile mineru-local up -d
```

### 4.2 临时测试

```bash
# 临时使用云服务测试（不修改 .env）
MINERU_MODE=cloud MINERU_PIPELINE_ID=xxx docker-compose up -d

# 临时使用本地服务测试
MINERU_MODE=local docker-compose --profile mineru-local up -d
```

## 5. Pipeline ID 获取

### 5.1 创建 Pipeline

```
步骤：
1. 访问 https://mineru.net
2. 注册/登录账号
3. 进入"Pipeline 管理"
4. 点击"创建 Pipeline"
5. 配置处理流程:
   - 选择处理步骤（解析、分割、提取）
   - 配置 OCR 语言
   - 其他参数保持默认
6. 点击"部署"
7. 复制 Pipeline ID（UUID 格式）
```

### 5.2 Pipeline 管理

```
限制：
- 每个 Pipeline 最多 10 个文件
- 单个文件最大 100MB
- 单个文件最多 10 页

建议：
- 定期清理旧文件
- 或创建多个 Pipeline 轮换使用
```

## 6. 配置验证

### 6.1 启动时检查

```python
# 应用启动时会验证配置
# 检查项：
1. mineru_mode 必须是 "cloud" 或 "local"
2. cloud 模式下 pipeline_id 不能为空
3. timeout_seconds 必须 >= 0
4. poll_interval 必须 > 0
```

### 6.2 手动验证

```bash
# 验证云服务配置
curl -X GET "https://mineru.net/api/kie/restful/pipelines/${MINERU_PIPELINE_ID}/result"

# 验证本地服务配置
curl http://localhost:8001/docs  # MinerU API 文档页面
```

## 7. 故障排查

### 7.1 常见配置错误

| 错误现象 | 可能原因 | 解决方案 |
|----------|----------|----------|
| "Cloud mode enabled but no pipeline_id provided" | 云服务模式未配置 Pipeline ID | 检查 .env 中 MINERU_PIPELINE_ID 是否设置 |
| "Connection refused to mineru-api:8000" | 本地模式但容器未启动 | 使用 `--profile mineru-local` 启动 |
| "Invalid pipeline_id" | Pipeline ID 错误或未部署 | 检查 Pipeline ID 是否正确，Pipeline 是否已部署 |
| "Timeout waiting for result" | 处理超时 | 增加 timeout_seconds 或检查文件是否过大 |
| "File too large (XXX MB)" | 文件超过云服务限制 | 切换到本地模式或压缩文件 |

### 7.2 日志检查

```bash
# 查看 celery-worker 日志
docker-compose logs -f celery-worker

# 查看 mineru-api 日志（本地模式）
docker-compose logs -f mineru-api

# 关键日志示例
"MinerU 云服务在熔断期，跳过"  # 云服务不可达，已启用熔断
"MinerU response missing markdown content"  # 云服务返回格式异常
"文件过大 (XXX MB)，云服务限制为 100MB"  # 文件超限
```

## 8. 性能调优

### 8.1 超时配置建议

| 场景 | timeout_seconds | poll_interval | 说明 |
|------|----------------|---------------|------|
| 云服务，小文件 | 60 | 3 | 快速响应 |
| 云服务，中等文件 | 180 | 5 | 平衡性能 |
| 云服务，大文件 | 300 | 10 | 避免频繁轮询 |
| 本地 CPU | 0 | N/A | 无限等待 |
| 本地 GPU | 120 | N/A | 适度等待 |

### 8.2 并发控制

```bash
# 云服务模式
# 无需配置，云端自动控制并发

# 本地 CPU 模式
# 在 docker-compose.yml 中配置
MINERU_API_MAX_CONCURRENT_REQUESTS=1

# 本地 GPU 模式
# 根据显存大小调整
MINERU_API_MAX_CONCURRENT_REQUESTS=2
```

### 8.3 网络优化

```bash
# 云服务模式，网络不稳定时
# 增加重试次数和超时时间
MINERU_CLOUD_TIMEOUT=600
# 或启用熔断机制（已内置）
```

## 9. 安全建议

### 9.1 敏感信息保护

```bash
# Pipeline ID 是敏感信息，不应提交到版本控制
# .gitignore 应包含：
.env
.env.local

# 团队共享时使用 .env.example
# 每个开发者自行配置 .env
```

### 9.2 API 访问控制

```bash
# 云服务使用 Pipeline ID 认证
# 本地服务建议配置内网访问限制
# 在生产环境中，考虑添加 API Gateway 或防火墙规则
```
