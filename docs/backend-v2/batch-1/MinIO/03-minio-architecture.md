# MinIO 架构: Docker 集成与运维配置

本文档描述 MinIO 对象存储服务在项目 Docker Compose 环境中的集成方式、桶设计、SDK 依赖和运维操作。

---

## 1. Docker Compose 集成

### 1.1 服务定义

在现有 `docker-compose.yml` 中新增 MinIO 服务，使用 `profiles` 机制实现可选启用:

```yaml
services:
  # ... 现有服务 (postgres, redis, elasticsearch, celery-worker) ...

  minio:
    image: quay.io/minio/minio:latest
    container_name: newbee-minio
    ports:
      - "${MINIO_API_PORT:-9000}:9000"        # S3 API 端口
      - "${MINIO_CONSOLE_PORT:-9001}:9001"    # Web 管理控制台
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY:-minioadmin123}
      MINIO_SERVER_URL: "http://localhost:${MINIO_API_PORT:-9000}"
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    profiles:
      - minio
    networks:
      - default

volumes:
  minio_data:      # MinIO 数据持久化
  # ... 现有 volumes ...
```

### 1.2 关键配置说明

| 配置项 | 值 | 说明 |
|--------|------|------|
| `image` | `quay.io/minio/minio:latest` | MinIO 官方镜像，从 Quay.io 拉取 |
| `ports: 9000` | S3 API | Python SDK 和浏览器 Presigned URL 访问此端口 |
| `ports: 9001` | Web Console | 浏览器管理界面，可视化管理桶和对象 |
| `MINIO_SERVER_URL` | `http://localhost:9000` | Presigned URL 的基础地址，必须是浏览器可达的地址 |
| `volumes: minio_data` | Named Volume | 数据持久化，`docker compose down` 不丢数据，`down -v` 才清除 |
| `profiles: minio` | 可选启用 | 开发环境默认不启动，需要时 `docker compose --profile minio up -d` |

### 1.3 profiles 机制

`profiles` 与项目中已有的 `mineru-local`、`monitor`、`debug` 等 profile 一致。开发者根据需要选择启动组合:

```bash
# 仅后端核心服务 (默认，使用本地文件系统)
docker compose up -d

# 启用 MinIO 存储
docker compose --profile minio up -d

# 启用 MinIO + 本地 MinerU
docker compose --profile minio --profile mineru-local up -d

# 启用全部可选服务
docker compose --profile minio --profile mineru-local --profile monitor --profile debug up -d
```

### 1.4 网络拓扑

```
                    Docker Network (default)
                    +-----------------------+
                    |                       |
  Browser -----9000--->  MinIO :9000        |  <--- Presigned URL 直接访问
          -----9001--->  MinIO :9001        |  <--- Web Console
          -----8000--->  FastAPI (宿主机)   |
                    |                       |
                    |  Celery Worker -------|---> MinIO :9000 (内部上传)
                    |       |              |
                    |       +---> PostgreSQL|
                    |       +---> Redis    |
                    |       +---> ES       |
                    +-----------------------+
```

Celery Worker 在 Docker 内部通过容器名 `minio:9000` 访问 MinIO 服务。FastAPI 在宿主机通过 `localhost:9000` 访问。浏览器通过端口映射 `localhost:9000` 直接获取文件。

---

## 2. 桶设计

### 2.1 单桶策略

使用单个桶 `documents` 存储所有文档文件，通过对象键前缀组织:

```
documents/                          (桶)
├── 393f579b-.../                    (document_id 前缀)
│   ├── original/paper.pdf
│   ├── markdown/content.md
│   └── assets/
│       ├── images/a267b5...jpg
│       ├── images/bb97ab...jpg
│       └── meta/layout.json
├── 3bebffae-.../
│   ├── original/report.pdf
│   ├── markdown/content.md
│   └── assets/images/...
└── ...
```

### 2.2 为什么选择单桶而非多桶

| 维度 | 单桶 (按前缀) | 多桶 (按 document_id) |
|------|---------------|----------------------|
| 管理复杂度 | 低，一个桶统一策略 | 高，每个文档一个桶 |
| IAM 策略 | 一条桶策略覆盖 | 需要动态创建桶策略 |
| 清理操作 | `delete_prefix("393f579b-.../")`  | `remove_bucket("393f579b-...")` |
| 列表查询 | `list_objects(prefix="393f579b-...")` | `list_objects()` 即可 |
| MinIO 限制 | 无限制 | MinIO 对桶数量无硬限制但不推荐过多 |

单桶方案更简单，且与现有文件系统的目录结构完全对应。

### 2.3 桶策略

默认不设置公开读取策略。所有文件访问通过 Presigned URL 或 SDK 认证调用:

```python
# 如需设置公开读取 (不推荐用于文档存储，仅供参考)
# policy = {
#     "Version": "2012-10-17",
#     "Statement": [{
#         "Effect": "Allow",
#         "Principal": {"AWS": ["*"]},
#         "Action": ["s3:GetObject"],
#         "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
#     }]
# }
```

---

## 3. Python SDK 依赖

### 3.1 安装

```bash
pip install minio>=7.2.0
```

添加到 `requirements.txt`:

```
# 对象存储 (可选，仅 STORAGE_BACKEND=minio 时需要)
minio>=7.2.0
```

### 3.2 最低 Python 版本要求

`minio-py` 7.x 要求 Python 3.10+。项目当前使用 Python 3.11，满足要求。

### 3.3 连接池

MinIO Python SDK 内部使用 `urllib3` 连接池，默认配置适用于大多数场景。如需调整:

```python
import urllib3

http_client = urllib3.PoolManager(
    num_pools=10,
    maxsize=10,
    cert_reqs="CERT_NONE",  # 开发环境禁用 SSL 验证
)

client = Minio(
    endpoint="localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin123",
    secure=False,
    http_client=http_client,
)
```

---

## 4. 环境变量汇总

### 4.1 新增环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `STORAGE_BACKEND` | `local` | 存储后端类型: `local` 或 `minio` |
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO S3 API 地址 |
| `MINIO_ACCESS_KEY` | `minioadmin` | 访问密钥 (同 MINIO_ROOT_USER) |
| `MINIO_SECRET_KEY` | `minioadmin123` | 秘密密钥 (同 MINIO_ROOT_PASSWORD) |
| `MINIO_BUCKET` | `documents` | 桶名称 |
| `MINIO_SECURE` | `false` | 是否使用 HTTPS |
| `MINIO_PUBLIC_ENDPOINT` | (同 MINIO_ENDPOINT) | 浏览器可达的 MinIO 地址 |
| `MINIO_API_PORT` | `9000` | 宿主机映射的 API 端口 |
| `MINIO_CONSOLE_PORT` | `9001` | 宿主机映射的控制台端口 |

### 4.2 .env.example 追加

```bash
# === 存储后端 ===
# 可选值: local (默认，使用本地文件系统) 或 minio (使用 MinIO 对象存储)
STORAGE_BACKEND=local

# === MinIO 配置 (仅 STORAGE_BACKEND=minio 时需要) ===
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_BUCKET=documents
MINIO_SECURE=false
# MINIO_PUBLIC_ENDPOINT=localhost:9000
# MINIO_API_PORT=9000
# MINIO_CONSOLE_PORT=9001
```

### 4.3 Celery Worker 环境变量传递

Celery Worker 运行在 Docker 容器内，需要传递 MinIO 配置:

```yaml
services:
  celery-worker:
    environment:
      # ... 现有配置 ...
      STORAGE_BACKEND: ${STORAGE_BACKEND:-local}
      MINIO_ENDPOINT: ${MINIO_ENDPOINT:-minio:9000}    # 注意: 容器内使用 minio 主机名
      MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY:-minioadmin}
      MINIO_SECRET_KEY: ${MINIO_SECRET_KEY:-minioadmin123}
      MINIO_BUCKET: ${MINIO_BUCKET:-documents}
```

注意 `MINIO_ENDPOINT` 在 Celery Worker 中应使用 Docker 内部地址 `minio:9000`，而非 `localhost:9000`。

---

## 5. Web 管理控制台

MinIO 提供内置的 Web 管理控制台，可在 `http://localhost:9001` 访问:

### 5.1 功能

- 浏览桶和对象 (类似文件管理器)
- 上传/下载/删除对象
- 管理桶策略和访问规则
- 查看服务状态和监控指标
- 管理用户和访问密钥

### 5.2 开发场景用途

- 验证 Celery Worker 上传的文件是否正确
- 检查 MinerU 转换后的图片是否完整
- 手动删除测试数据
- 替代文件管理器直接浏览 MinIO `documents/` 桶前缀的角色（而不是再依赖旧的 `data/documents/`）

---

## 6. 运维操作

### 6.1 mc (MinIO Client) 命令行工具

MinIO 镜像内置 `mc` 命令行工具，可通过 `docker exec` 执行:

```bash
# 设置别名
docker exec newbee-minio mc alias set local http://localhost:9000 minioadmin minioadmin123

# 列出桶
docker exec newbee-minio mc ls local/

# 列出某个文档的所有文件
docker exec newbee-minio mc ls --recursive local/documents/393f579b-2318-42eb-8a0a-9b5232900108/

# 查看桶大小统计
docker exec newbee-minio mc du local/documents/

# 删除某个文档的所有文件
docker exec newbee-minio mc rm --recursive --force local/documents/393f579b-2318-42eb-8a0a-9b5232900108/

# 将 MinIO 中的某个 Markdown 拉到容器临时目录排查
docker exec newbee-minio mc cp local/documents/393f579b-.../markdown/content.md /tmp/393f579b-content.md
```

### 6.2 数据备份

```bash
# 镜像整个桶到本地目录
docker exec newbee-minio mc mirror local/documents/ /backup/documents/

# 从备份恢复
docker exec newbee-minio mc mirror /backup/documents/ local/documents/
```

### 6.3 与 make clean-doc 的对应关系

当使用 MinIO 后端时，现有的清理工具需要适配:

| 操作 | Bind Mount 方式 | MinIO 方式 |
|------|-----------------|------------|
| 精确删除 | `make clean-doc ID=xxx` | `storage.delete_prefix("xxx/")` 或 `mc rm --recursive` |
| 孤儿检测 | 扫描 `data/documents/` 目录 | `storage.list_objects("")` 获取所有前缀 |
| 环境重建 | `rm -rf data/documents/*` | `mc rm --recursive --force local/documents/` |

清理工具的 MinIO 适配将在迁移阶段实现，优先级低于核心存储层改造。

---

## 7. 资源占用评估

| 指标 | 估计值 | 说明 |
|------|--------|------|
| 镜像大小 | ~200 MB | `quay.io/minio/minio:latest` |
| 运行内存 | ~128-256 MB | 单节点默认配置 |
| CPU 占用 | 极低 (空闲时) | 仅在文件操作时消耗 |
| 磁盘 | 与数据量成正比 | Named Volume，与 Bind Mount 相当 |

在项目现有的 Docker Compose 环境中 (PostgreSQL + Redis + Elasticsearch + Celery)，新增 MinIO 的资源开销可接受。

MinIO 与前端的具体集成方案见 [04-frontend-integration.md](./04-frontend-integration.md)。
