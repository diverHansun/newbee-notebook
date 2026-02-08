# Docker 配置变更

## 1. 变更概述

### 1.1 核心变更

| 变更项 | 原配置 | 新配置 | 影响 |
|--------|--------|--------|------|
| mineru-api 依赖 | 强依赖 | 条件依赖（profile） | 默认启动更快 |
| celery-worker depends_on | 包含 mineru-api | 移除 mineru-api | 云服务模式无需本地容器 |
| 默认启动模式 | 本地服务 | 云服务 | 无需启动 mineru-api |
| Profile 支持 | 无 | mineru-local | 按需启用本地服务 |

### 1.2 启动方式对比

**原方式**：

```bash
docker-compose up -d
# 启动: postgres, redis, es, celery-worker, mineru-api
# 问题: mineru-api 常驻内存，即使不使用
```

**新方式**：

```bash
# 默认（云服务）
docker-compose up -d
# 启动: postgres, redis, es, celery-worker
# mineru-api 不启动

# 本地模式
docker-compose --profile mineru-local up -d
# 启动: postgres, redis, es, celery-worker, mineru-api
```

## 2. docker-compose.yml 变更

### 2.1 celery-worker 服务

**变更点**：

```yaml
services:
  celery-worker:
    # ... 其他配置保持不变 ...

    environment:
      # ... 现有环境变量 ...

      # 新增: MinerU 模式配置
      MINERU_MODE: ${MINERU_MODE:-cloud}
      MINERU_PIPELINE_ID: ${MINERU_PIPELINE_ID:-}

      # 修改: 本地 API URL（仅本地模式使用）
      MINERU_API_URL: ${MINERU_LOCAL_API_URL:-http://mineru-api:8000}

    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
      elasticsearch:
        condition: service_healthy
      # 移除: mineru-api 依赖
      # mineru-api:
      #   condition: service_healthy
```

**完整配置**：

```yaml
celery-worker:
  image: python:3.11-slim
  container_name: medimind-celery-worker
  working_dir: /app
  volumes:
    - ./:/app
  command: >
    bash -c "pip install -q -r requirements.txt && \
             celery -A medimind_agent.infrastructure.tasks.celery_app worker --loglevel=info"
  env_file:
    - .env
  environment:
    CELERY_BROKER_URL: redis://redis:6379/0
    CELERY_RESULT_BACKEND: redis://redis:6379/0
    REDIS_HOST: redis
    POSTGRES_HOST: postgres
    ELASTICSEARCH_URL: http://elasticsearch:9200
    DOCUMENTS_DIR: ${DOCUMENTS_DIR:-data/documents}
    PROCESS_UPLOAD_SYNC: ${PROCESS_UPLOAD_SYNC:-false}

    # MinerU 配置
    MINERU_ENABLED: ${MINERU_ENABLED:-true}
    MINERU_MODE: ${MINERU_MODE:-cloud}
    MINERU_PIPELINE_ID: ${MINERU_PIPELINE_ID:-}
    MINERU_LOCAL_API_URL: ${MINERU_LOCAL_API_URL:-http://mineru-api:8000}
    MINERU_BACKEND: ${MINERU_BACKEND:-pipeline}
    MINERU_LANG_LIST: ${MINERU_LANG_LIST:-ch}

  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_started
    elasticsearch:
      condition: service_healthy

  networks:
    - medimind_network
  restart: unless-stopped
```

### 2.2 mineru-api 服务

**变更点**：

```yaml
services:
  mineru-api:
    # ... 所有配置保持不变 ...

    # 新增: Profile 配置
    profiles:
      - mineru-local
```

**完整配置**：

```yaml
mineru-api:
  build:
    context: ./docker/mineru
    dockerfile: Dockerfile.cpu
  image: medimind/mineru-api:cpu
  container_name: medimind-mineru-api
  restart: unless-stopped
  environment:
    MINERU_MODEL_SOURCE: modelscope
    MINERU_DEVICE_MODE: cpu
    MINERU_API_ENABLE_FASTAPI_DOCS: ${MINERU_API_ENABLE_FASTAPI_DOCS:-1}
    MINERU_API_MAX_CONCURRENT_REQUESTS: ${MINERU_API_MAX_CONCURRENT_REQUESTS:-1}
  volumes:
    - mineru_cache:/root/.cache
  ports:
    - "8001:8000"
  networks:
    - medimind_network
  healthcheck:
    test: ["CMD-SHELL", "curl -f http://localhost:8000/docs >/dev/null 2>&1 || exit 1"]
    interval: 30s
    timeout: 10s
    retries: 10

  # 新增: Profile 配置
  profiles:
    - mineru-local
```

## 3. docker-compose.gpu.yml 变更

### 3.1 celery-worker 覆盖（移除）

**原配置**：

```yaml
services:
  celery-worker:
    environment:
      DOCUMENTS_DIR: ${DOCUMENTS_DIR:-data/documents}
      MINERU_BACKEND: hybrid-auto-engine
```

**新配置**：

```yaml
# 移除 celery-worker 覆盖
# 环境变量通过 .env 文件统一管理
```

### 3.2 mineru-api 覆盖（保持）

**配置保持**：

```yaml
services:
  mineru-api:
    build:
      context: ./docker/mineru
      dockerfile: Dockerfile.gpu
    image: medimind/mineru-api:gpu
    environment:
      MINERU_MODEL_SOURCE: modelscope
      MINERU_DEVICE_MODE: cuda
      MINERU_API_ENABLE_FASTAPI_DOCS: ${MINERU_API_ENABLE_FASTAPI_DOCS:-1}
      MINERU_API_MAX_CONCURRENT_REQUESTS: ${MINERU_API_MAX_CONCURRENT_REQUESTS:-2}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    ipc: host
    shm_size: "32gb"
    ulimits:
      memlock: -1
      stack: 67108864

    # 继承 profile 配置
    profiles:
      - mineru-local
```

## 4. 启动命令详解

### 4.1 云服务模式（默认）

```bash
# 配置环境变量
export MINERU_MODE=cloud
export MINERU_PIPELINE_ID=your-pipeline-id

# 启动服务
docker-compose up -d

# 验证
docker-compose ps
# 输出应该包含:
#   medimind-postgres
#   medimind-redis
#   medimind-elasticsearch
#   medimind-celery-worker
# 不包含:
#   medimind-mineru-api
```

### 4.2 本地 CPU 模式

```bash
# 配置环境变量
export MINERU_MODE=local
export MINERU_BACKEND=pipeline

# 启动服务（启用 profile）
docker-compose --profile mineru-local up -d

# 验证
docker-compose ps
# 输出应该包含:
#   medimind-postgres
#   medimind-redis
#   medimind-elasticsearch
#   medimind-celery-worker
#   medimind-mineru-api  <-- 已启动
```

### 4.3 本地 GPU 模式

```bash
# 配置环境变量
export MINERU_MODE=local
export MINERU_BACKEND=hybrid-auto-engine

# 启动服务（多配置文件 + profile）
docker-compose \
  -f docker-compose.yml \
  -f docker-compose.gpu.yml \
  --profile mineru-local \
  up -d

# 验证 GPU
docker exec medimind-mineru-api nvidia-smi
```

### 4.4 停止服务

```bash
# 停止所有服务
docker-compose down

# 停止并删除 volume
docker-compose down -v

# 停止特定 profile
docker-compose --profile mineru-local down
```

## 5. Profile 机制详解

### 5.1 什么是 Profile

```
Docker Compose Profile 用于分组服务：
- 默认情况下，只启动没有 profile 的服务
- 使用 --profile 参数可以启用特定 profile 的服务
- 一个服务可以属于多个 profile
```

### 5.2 应用场景

| 场景 | Profile | 启动的服务 |
|------|---------|-----------|
| 开发环境（云服务） | 无 | 基础服务 |
| 开发环境（本地） | mineru-local | 基础服务 + mineru-api |
| 调试 Kibana | debug | 基础服务 + kibana |
| 监控 Celery | monitor | 基础服务 + flower |

### 5.3 组合使用

```bash
# 同时启用多个 profile
docker-compose \
  --profile mineru-local \
  --profile monitor \
  up -d

# 启动:
#   基础服务 + mineru-api + flower
```

## 6. 环境变量传递

### 6.1 变量流向

```
.env 文件
   │
   ▼
docker-compose.yml (环境变量替换)
   │
   ▼
容器内环境变量
   │
   ▼
Python 应用读取
   │
   ▼
document_processing.yaml (变量替换)
```

### 6.2 关键环境变量

**celery-worker 容器**：

```yaml
environment:
  # 模式选择
  MINERU_MODE: ${MINERU_MODE:-cloud}

  # 云服务配置（mode=cloud 时使用）
  MINERU_PIPELINE_ID: ${MINERU_PIPELINE_ID:-}

  # 本地服务配置（mode=local 时使用）
  MINERU_LOCAL_API_URL: ${MINERU_LOCAL_API_URL:-http://mineru-api:8000}
  MINERU_BACKEND: ${MINERU_BACKEND:-pipeline}
  MINERU_LANG_LIST: ${MINERU_LANG_LIST:-ch}
```

### 6.3 变量验证

```bash
# 检查容器内环境变量
docker exec medimind-celery-worker env | grep MINERU

# 输出示例（云服务模式）：
# MINERU_MODE=cloud
# MINERU_PIPELINE_ID=550e8400-e29b-41d4-a716-446655440000

# 输出示例（本地模式）：
# MINERU_MODE=local
# MINERU_LOCAL_API_URL=http://mineru-api:8000
# MINERU_BACKEND=pipeline
```

## 7. 健康检查

### 7.1 服务健康检查

**mineru-api**：

```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -f http://localhost:8000/docs >/dev/null 2>&1 || exit 1"]
  interval: 30s
  timeout: 10s
  retries: 10
```

**验证健康状态**：

```bash
docker-compose ps

# 输出示例:
# NAME                      STATUS
# medimind-mineru-api       Up (healthy)
# medimind-celery-worker    Up
```

### 7.2 手动健康检查

```bash
# 检查 mineru-api（本地模式）
curl http://localhost:8001/docs

# 检查 celery-worker
docker exec medimind-celery-worker \
  celery -A medimind_agent.infrastructure.tasks.celery_app inspect ping
```

## 8. 故障排查

### 8.1 常见问题

**问题 1：云服务模式下 celery-worker 报错 "Connection refused to mineru-api"**

```
原因: 配置错误，应该是 mode=local 但环境变量仍指向本地 API

解决:
1. 检查 .env 中 MINERU_MODE 是否为 cloud
2. 检查代码是否正确处理 mode 分支
```

**问题 2：本地模式下 mineru-api 容器未启动**

```
原因: 未使用 --profile mineru-local 参数

解决:
docker-compose --profile mineru-local up -d
```

**问题 3：GPU 模式下报错 "nvidia-smi not found"**

```
原因: 未安装 nvidia-container-toolkit

解决:
1. 安装 nvidia-container-toolkit
2. 重启 Docker 服务
3. 验证: docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
```

### 8.2 日志查看

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f celery-worker
docker-compose logs -f mineru-api

# 查看最近 100 行
docker-compose logs --tail=100 celery-worker
```

### 8.3 强制重建

```bash
# 重建并启动（云服务模式）
docker-compose up -d --build

# 重建并启动（本地模式）
docker-compose --profile mineru-local up -d --build

# 仅重建 mineru-api
docker-compose build mineru-api
```

## 9. 资源占用对比

### 9.1 内存占用

| 模式 | 容器 | 内存占用 | 说明 |
|------|------|----------|------|
| 云服务 | celery-worker | ~200MB | 基础 Python 环境 |
| 本地 CPU | celery-worker | ~200MB | 同上 |
| 本地 CPU | mineru-api | ~2GB | 包含 MinerU 模型 |
| 本地 GPU | celery-worker | ~200MB | 同上 |
| 本地 GPU | mineru-api | ~6GB | GPU 模式 + 模型 |

### 9.2 启动时间对比

| 模式 | 首次启动 | 后续启动 | 说明 |
|------|----------|----------|------|
| 云服务 | ~30s | ~10s | 无需启动 mineru-api |
| 本地 CPU | ~5min | ~30s | 首次需下载模型 |
| 本地 GPU | ~8min | ~45s | 首次需下载模型和 GPU 镜像 |

### 9.3 资源优化建议

**云服务模式**：

```
优势: 无本地资源占用
适用: 大多数场景
```

**本地 CPU 模式**：

```
优势: 离线可用
劣势: 内存占用高，处理慢
建议: 仅在无外网或测试时使用
```

**本地 GPU 模式**：

```
优势: 高速处理
劣势: 显存占用高
建议: 高并发或大批量处理场景
```
