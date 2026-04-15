# Newbee Notebook — 快速开始

这份文档会带你从零开始跑通整个项目。如果你只是想最快速度体验一下，直接看 [README 的快速启动](README.md#快速启动) 就够了。

这里是完整版，涵盖本地开发、Docker 部署、GPU 模式、存储后端等所有配置选项。

---

## 目录

- [环境要求](#环境要求)
- [安装依赖（本地开发）](#安装依赖本地开发)
- [配置环境变量](#配置环境变量)
- [启动服务（Docker）](#启动服务docker)
- [启动 FastAPI 应用（本地开发）](#启动-fastapi-应用本地开发)
- [验证服务](#验证服务)
- [常用命令](#常用命令)
- [可选：监控工具](#可选监控工具)
- [可选：初始化数据索引](#可选初始化数据索引)
- [常见问题](#常见问题)

---

## 环境要求

### 软件依赖

| 依赖 | 版本 | 说明 |
|---|---|---|
| Docker & Docker Compose | 最新版 | 所有基础设施服务通过 Docker 运行 |
| Python | 3.11+ | 本地开发时需要（Docker 部署可跳过） |
| Node.js | 18+ | 前端本地开发时需要（Docker 部署可跳过） |

补充说明：
- Windows / macOS：建议使用 Docker Desktop
- Linux：建议使用 Docker Engine + Docker Compose Plugin

### 硬件要求与启动模式选择

根据机器配置选择合适的部署模式：

#### 按设备快速选路

| 你的设备 | 推荐启动方式 | 是否支持官方本地 GPU 加速 | 说明 |
|---|---|---|---|
| Windows / macOS / Linux 普通笔记本或台式机（无独显、仅集显） | **默认 Docker 模式** | 否 | 最推荐，直接用云端 MinerU + API Embedding |
| Apple Silicon Mac / Intel Mac | **默认 Docker 模式** | 否 | 当前仓库没有提供 Metal 本地加速覆盖配置 |
| AMD / Intel GPU 设备 | **默认 Docker 模式** | 否 | 当前仓库没有提供 ROCm / oneAPI 本地加速覆盖配置 |
| NVIDIA GPU，显存 ≥ 8GB，内存 ≥ 32GB | **GPU 本地增强模式** | 是 | 可使用本地 MinerU + 本地 Embedding |
| 无 GPU，但希望 MinerU 和 Embedding 全部本地运行 | **手工扩展 CPU 全本地** | 否 | 当前无官方一键 Compose，不推荐 |

| 模式 | 显存 | 内存 | 说明 |
|---|---|---|---|
| **默认 Docker 模式**（推荐） | 无要求 | 8GB+ | `docker compose up -d`，默认使用云端 MinerU、API Embedding、MinIO |
| **GPU 本地增强模式** | NVIDIA，≥ 8GB 显存 | ≥ 32GB | `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build`，支持本地 MinerU 与本地 Embedding |
| **纯 CPU 全本地**（不推荐） | 无独立显卡 | ≥ 32GB | 如需同时本地跑 MinerU 和本地 Embedding，需要额外手工扩展 CPU 版服务，仓库当前不提供官方一键 Compose |

> GPU 模式会为 `mineru-api` 容器分配 32GB 共享内存、为 `celery-worker` 容器分配 16GB 共享内存，请确保系统内存充裕。
> 默认模式下首次启动会构建 `api` 与 `celery-worker` 镜像，并在构建阶段安装 Python 依赖。CPU 模式会安装 CPU 版 torch；后续重启容器不会再重复 `pip install`。如果你改了 `requirements.txt`，请重新执行 `docker compose up -d --build`。
> 没有独立显卡并不意味着你必须走“纯 CPU 全本地”。对大多数无 GPU 设备，默认 Docker 模式就是正确选择。

---

## 安装依赖（本地开发）

> 如果你只使用 Docker 部署，可以跳过这一节。

### 1. 安装 uv（推荐的 Python 包管理器）

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

或通过 pip 安装：
```bash
pip install uv
```

### 2. 同步项目依赖

```bash
# 安装所有依赖（自动创建虚拟环境）
uv sync

# 激活虚拟环境
# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. 可选：本地 Embedding GPU 加速

如果你使用本地 Embedding 模型且机器有独立 GPU，可按 [PyTorch 官方指引](https://pytorch.org/get-started/locally/) 安装与本机 CUDA 匹配的 `torch` 版本。主要使用云端 Embedding API 的话不需要装。

检查 `torch` 是否启用 CUDA：

```bash
python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available())"
```

---

## 配置环境变量

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

macOS / Linux / Git Bash：

```bash
cp .env.example .env
```

编辑 `.env` 文件，以下是各部分的配置说明。

### LLM 服务（必填，建议都配置）

```bash
# 智谱 AI — 获取 API Key：https://open.bigmodel.cn/
ZHIPU_API_KEY=your_key_here

# 通义千问 — 获取 API Key：https://bailian.console.aliyun.com/
DASHSCOPE_API_KEY=your_key_here
```

### 运行时切换面板（可选但推荐）

如果你希望在前端设置面板或 `/api/v1/config/*` 接口中切换 LLM、Embedding、ASR、MinerU，请开启：

```bash
FEATURE_MODEL_SWITCH=true
```

### 数据库（必填）

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=newbee_notebook
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

### MinerU 文档解析

PDF 解析依赖 [MinerU](https://github.com/opendatalab/MinerU)，支持 cloud 和 local 两种模式。

**默认 Docker 模式（推荐，开箱即用）：**

```bash
MINERU_ENABLED=true
MINERU_MODE=cloud
# 获取 API Key：https://mineru.net/apiManage/token
MINERU_API_KEY=your_key_here
```

说明：
- `docker compose up -d` 默认固定为云端 MinerU，不会拉起本地 `mineru-api` 容器。
- 只有 GPU 覆盖栈才内置了本地 `mineru-api` 容器与 `MINERU_LOCAL_ENABLED=true`，可在设置面板中切换 `cloud/local`。
- 纯 CPU 机器如果想本地跑 MinerU，需要自行准备 CPU 版 `mineru-api` 服务；这条路径至少建议 32GB 内存，且不推荐。
- 如果开启 Clash Verge 或系统代理后，`cdn-mineru.openxlab.org.cn` 报 `UNEXPECTED_EOF_WHILE_READING` / `curl: (35) TLS connect error`，说明问题已经发生在 OpenXLab CDN 的 TLS 握手阶段，单纯给 Docker 容器补 `HTTP_PROXY` 不一定能修复。优先在 Clash 中给 `cdn-mineru.openxlab.org.cn`、`openxlab.org.cn` 配置 DIRECT 规则；只有在你已经准备好可访问的本地 `mineru-api` 服务时，才建议切到 `MINERU_MODE=local`。仅修改这个变量并不会自动绕过 CDN；如果本地 MinerU 不可用，PDF 最终仍可能回退到 MarkItDown。

**GPU 本地模式（随 GPU 覆盖栈使用）：**

```bash
MINERU_MODE=local
MINERU_LOCAL_API_URL=http://localhost:8001
MINERU_BACKEND=hybrid-auto-engine
MINERU_LANG_LIST=ch,en
MINERU_LOCAL_TIMEOUT=0
```

**纯 CPU 全本地模式（仅供手工扩展参考，不推荐）：**

```bash
MINERU_MODE=local
MINERU_LOCAL_API_URL=http://localhost:8001
MINERU_BACKEND=pipeline
MINERU_LANG_LIST=ch,en
MINERU_LOCAL_TIMEOUT=0
```

### Torch 版本配置

默认 Docker 模式和 NVIDIA GPU 模式的配置方式不同：

- 默认 Docker 模式：通常不需要手动修改。若你确实要更换 CPU 版 torch，可在 `.env` 中设置 `PYTHON_RUNTIME_TORCH_VERSION=2.9.0`，然后重新执行 `docker compose up -d --build`。
- NVIDIA GPU 模式：不要单独修改 `torch==x.y.z`。请在 `.env` 中设置 `CELERY_WORKER_BASE_IMAGE=pytorch/pytorch:<torch+cuda-tag>`，例如 `pytorch/pytorch:2.9.0-cuda12.8-cudnn9-runtime`，再执行 `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build`。
- Apple Silicon、AMD GPU、Intel GPU：当前仓库没有官方本地 GPU 加速覆盖配置，建议继续使用默认 Docker 模式。

选择原则：
- 你关心 CPU 模式能不能跑：通常不用改 torch 版本，直接用默认 Docker 模式。
- 你关心 NVIDIA GPU 能不能本地加速：不要只看 torch 版本，要看 torch 与 CUDA 的组合是否和驱动匹配，因此优先改 `CELERY_WORKER_BASE_IMAGE`。
- 无论修改 `PYTHON_RUNTIME_TORCH_VERSION` 还是 `CELERY_WORKER_BASE_IMAGE`，都需要重新执行带 `--build` 的启动命令，让镜像重新构建。

### 存储后端

通过 Docker Compose 启动时，默认使用 **MinIO 对象存储**（`docker-compose.yml` 已内置 MinIO 服务）。开发者在宿主机本地运行 FastAPI / `pnpm dev` 时，也建议继续使用同一个 MinIO，这样链路与 Docker 运行时保持一致。

```bash
# 运行时默认：MinIO（Docker 和本地 FastAPI 调试都使用这一套）
STORAGE_BACKEND=minio
MINIO_ENDPOINT=localhost:9000
MINIO_PUBLIC_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123   # 生产环境请务必修改
```

补充说明：
- `.env` 中的 `MINIO_ENDPOINT` / `MINIO_PUBLIC_ENDPOINT` 应保持为宿主机可访问地址（通常是 `localhost:9000`）。
- `docker-compose.yml` 会为容器内的 API / worker 自动覆盖 `MINIO_ENDPOINT=minio:9000`，因此仍然兼容全 Docker 启动。
- `MINIO_PUBLIC_ENDPOINT` 是浏览器访问预签名 URL 的外部地址。在 Docker Desktop 本地开发下，通常保持 `localhost:9000` 即可。

### 文件处理策略

| 文件类型 | 处理链路 |
|---|---|
| PDF | MinerU（cloud / local）→ PyPDF fallback |
| CSV / Word / TXT / MD / HTML 等 | MarkItDown → Markdown |

默认 Docker 部署和宿主机 FastAPI 调试都会把处理后的文件存储在 MinIO 的 `documents` bucket 中；只有离线脚本 / 测试显式切到 `STORAGE_BACKEND=local` 时，才会写入 `data/documents/{document_id}/`。

---

## 启动服务（Docker）

### 模式一：默认 Docker 模式（推荐，无特殊硬件要求）

这是当前仓库的默认一键启动方式。PDF 解析使用 MinerU 云端 API，Embedding 默认使用通义千问 API，存储使用 MinIO。需要配置 `MINERU_API_KEY` 和 `DASHSCOPE_API_KEY`。

```bash
docker compose up -d
```

首次启动会构建镜像，需要等待几分钟。启动完成后包含以下服务：

| 服务 | 端口 | 说明 |
|---|---|---|
| Frontend | 3000 | 前端界面 |
| API | 8000 | FastAPI 后端 |
| PostgreSQL + pgvector | 5432 | 关系数据库 + 向量存储 |
| Elasticsearch | 9200 | 全文检索 |
| Redis | 6379 | 缓存 + 消息队列 |
| MinIO | 9000 / 9001 | 文件对象存储 |
| Celery Worker | — | 异步文档处理 |

```bash
# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f
```

这个模式下：
- 不会启动本地 `mineru-api` 容器，MinerU 只能走云端。
- 如果开启了 `FEATURE_MODEL_SWITCH=true`，设置面板中 MinerU 不可切到本地。
- Embedding 默认是 API 模式；如果你已经准备了本地 Embedding 模型，仍可切到本地 CPU 模式。
- 适用于大多数设备，包括 Windows / macOS / Linux 的无 GPU 机器、Apple Silicon，以及当前没有官方 GPU 覆盖配置的 AMD / Intel GPU 设备。

### 模式二：GPU 本地增强模式（NVIDIA 显存 ≥ 8GB，系统内存 ≥ 32GB）

这个模式在默认 Docker 栈上叠加 GPU 覆盖配置：MinerU 与 Embedding 都可以走本地 GPU，也都可以在设置面板里切回云端/API。

适用范围说明：当前官方 GPU 覆盖只支持 NVIDIA CUDA。Apple Silicon、AMD GPU、Intel GPU 不在这一套覆盖配置内。

前置条件：安装 [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

建议在 `.env` 中设置：

```bash
MINERU_MODE=local
```

启动命令：

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

GPU 模式配置说明：
- Worker 默认使用 `pytorch/pytorch:2.9.0-cuda12.8-cudnn9-runtime` 镜像（对应 CUDA 12.8），Embedding 在 CUDA 上运行
- 可在 `.env` 中通过 `CELERY_WORKER_BASE_IMAGE` 覆盖默认 PyTorch/CUDA 镜像 tag，按你的 NVIDIA 驱动版本选择合适的 CUDA 版本
- 如果你只是想改默认 CPU 镜像里的 torch 版本，而不是切换 CUDA 版本，请改 `.env` 中的 `PYTHON_RUNTIME_TORCH_VERSION`
- Worker 依赖会在镜像构建阶段一次性安装完成，后续重启不会再次执行 `pip install`
- mineru-api 设置 `MINERU_VIRTUAL_VRAM_SIZE=8`，触发每次推理后清理显存，适配 8GB 显卡
- mineru-api 容器 `shm_size=32gb`，Worker 容器 `shm_size=16gb`，请确保系统内存充裕
- `MINERU_BACKEND` 默认为 `hybrid-auto-engine`
- 这个模式会新增本地 `mineru-api` 容器（端口 `8001`）

> **注意：PyTorch 镜像版本需与你的显卡驱动匹配。**
> 上述 `cuda12.8` 是默认配置，如果你的驱动不支持 CUDA 12.8，请在 `.env` 中设置 `CELERY_WORKER_BASE_IMAGE`，换成与你环境匹配的 PyTorch 镜像版本。
> - NVIDIA 显卡：参考 [PyTorch 官方安装页面](https://pytorch.org/get-started/locally/) 查询与驱动版本对应的镜像 tag
> - 其他品牌显卡（AMD / Intel）：请参照 [MinerU 的相关文档](https://github.com/opendatalab/MinerU) 了解支持情况

#### 下载本地 Embedding 模型

GPU 模式使用 [Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) 作为本地 Embedding 模型（约 1.2GB），需要在启动前下载到项目目录中。

模型文件放置路径：`models/Qwen3-Embedding-0.6B/`

**方式一：ModelScope（国内推荐，速度快）**

```bash
pip install modelscope
modelscope download --model Qwen/Qwen3-Embedding-0.6B --local_dir models/Qwen3-Embedding-0.6B
```

**方式二：Hugging Face**

```bash
pip install huggingface_hub
hf download Qwen/Qwen3-Embedding-0.6B --local-dir models/Qwen3-Embedding-0.6B
```

下载完成后，确认 `.env` 中的模型路径配置：

```bash
QWEN3_EMBEDDING_MODE=local
QWEN3_EMBEDDING_MODEL_PATH=models/Qwen3-Embedding-0.6B
QWEN3_EMBEDDING_DEVICE=cuda
```

### 模式三：纯 CPU 全本地（不推荐，当前无官方一键 Compose）

如果你的机器没有独立 GPU，但你希望 **同时** 在本地运行 MinerU 和本地 Embedding，请注意：
- 这不是当前仓库提供的默认 Docker 方案。
- 建议系统内存至少 `32GB`，否则体验通常较差。
- 你需要自行准备 CPU 版 `mineru-api` 服务与本地 Embedding 模型，因此文档这里不提供一键启动命令。

对于大多数无 GPU 机器，更推荐直接使用默认 Docker 模式；如果确实需要本地 Embedding，可在准备好模型后，把 Embedding 单独切到本地 CPU。

如果你的目标只是“没有 GPU 也能跑起来”，请不要选这一模式，直接使用“默认 Docker 模式”。

---

## 启动 FastAPI 应用（本地开发）

> 这一节适用于**不通过 Docker 运行后端 API**的场景。如果你用 `docker compose up -d` 启动了全部服务，API 已经在运行了，可以跳过。

推荐把它当作开发者调试链路使用，而不是面向普通用户的默认启动方式。

### 先启动 Docker 基础设施

默认硬件 / 云端 MinerU：

```bash
docker compose up -d postgres redis elasticsearch minio celery-worker
```

NVIDIA GPU 本地增强模式（保留本地 `mineru-api` 容器）：

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d postgres redis elasticsearch minio celery-worker mineru-api
```

补充说明：
- 这两条命令都不会启动 Docker 版 `api` / `frontend`，避免和本机 `FastAPI --reload` / `pnpm dev` 端口冲突。
- 共享一套 `.env` 时，宿主机 FastAPI 默认读取 `localhost` 地址；Docker 中的 API / worker 由 compose 自动覆盖为容器内地址。
- 如果你要在宿主机调试本地 MinerU 模式，请把 `.env` 中的 `MINERU_LOCAL_API_URL` 设为 `http://localhost:8001`；Docker 内 worker 仍会通过 compose 覆盖访问 `http://mineru-api:8000`。
- `celery-worker` 使用源码挂载，但 Celery 进程不会热重载 Python 模块；如果你修改了 `document_tasks.py`、`document_processing/` 或其它 worker 侧代码，请执行 `docker restart newbee-notebook-celery-worker` 再重试任务。

```bash
# 确保虚拟环境已激活
python main.py --reload --port 8000
```

| 参数 | 说明 |
|---|---|
| `--reload` | 开发模式，代码修改后自动重载 |
| `--host 0.0.0.0` | 允许外部访问 |
| `--workers 4` | 生产模式多进程（不能与 `--reload` 同时使用） |
| `--log-level debug` | 调试日志级别 |

启动成功后访问：

| 服务 | 地址 |
|---|---|
| Swagger API 文档 | http://localhost:8000/docs |
| ReDoc 文档 | http://localhost:8000/redoc |
| 健康检查 | http://localhost:8000/api/v1/health |

如需同时本机调试前端：

```bash
cd frontend
pnpm dev
```

前端默认会把 `/api/v1/*` 代理到 `http://localhost:8000`。如果你改过地址，请在 `frontend/.env.local` 中同步调整 `INTERNAL_API_URL`。

---

## 验证服务

### 检查 Docker 服务

```bash
# 查看所有容器状态
docker compose ps

# 测试 Elasticsearch
curl http://localhost:9200

# 如果启用了本地 MinerU
curl http://localhost:8001/docs

# 如果启用了 MinIO
curl http://localhost:9000/minio/health/live
```

### 测试 API

```bash
# 健康检查
curl http://localhost:8000/api/v1/health

# 浏览器访问 API 文档
# http://localhost:8000/docs
```

### 上传文档测试

推荐使用脚本上传，避免 Windows 命令行的文件名编码问题：

```bash
# 上传单个文件
python scripts/upload_documents.py "D:\docs\测试文档.pdf"

# 上传多个文件
python scripts/upload_documents.py "D:\docs\文档A.pdf" "D:\docs\文档B.docx"
```

---

## 常用命令

### Docker 管理

```bash
# 停止所有服务
docker compose down

# 重启特定服务
docker compose restart api

# 查看实时日志
docker compose logs -f celery-worker

# 清理并重启（会删除 PostgreSQL / Elasticsearch / Redis / MinIO 的 volumes）
docker compose down -v
docker compose up -d
```

### 数据清理（仅离线 / 测试显式使用 `STORAGE_BACKEND=local` 时）

```bash
# 清理孤儿目录（推荐）
make clean-orphans

# 按 document_id 精确删除
make clean-doc ID=<document_id>

# Windows PowerShell：
.\scripts\clean-doc.ps1 -Id <document_id>
```

默认 Docker + MinIO 模式通常不需要这些命令；它们主要用于本地文件系统存储链路。

---

## 可选：监控工具

```bash
# Celery 监控面板（Flower）
docker compose --profile monitor up -d flower
# 访问：http://localhost:5555

# Elasticsearch 可视化（Kibana）
docker compose --profile debug up -d kibana
# 访问：http://localhost:5601
```

---

## 可选：初始化数据索引

如果需要使用 RAG 检索功能，首次运行时需要构建索引：

```bash
# 构建 pgvector 向量索引
python -m newbee_notebook.scripts.rebuild_pgvector

# 构建 Elasticsearch 全文索引
python -m newbee_notebook.scripts.rebuild_es
```

---

## 常见问题

| 问题 | 解决方案 |
|---|---|
| 端口冲突 | 修改 `docker-compose.yml` 中的端口映射 |
| 依赖安装失败 | 尝试 `uv sync --reinstall` |
| Docker 服务启动慢 | 首次构建镜像需要时间；GPU 模式下本地 MinerU 首次启动还需下载模型 |
| GPU 不可用 | 确保安装了 [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)，或改用默认 Docker 模式 |
| Apple Silicon / AMD / Intel GPU 该选哪种模式 | 使用默认 Docker 模式；当前官方 GPU 覆盖只支持 NVIDIA CUDA |
| 没有独立显卡是不是要选“纯 CPU 全本地” | 不需要；大多数无 GPU 设备直接使用默认 Docker 模式即可 |
| 用户应该在哪里改 torch 版本 | 默认 Docker 模式改 `.env` 中的 `PYTHON_RUNTIME_TORCH_VERSION`；NVIDIA GPU 模式改 `.env` 中的 `CELERY_WORKER_BASE_IMAGE` |
| 本地模式仍走云端或 PDF 仍回退到 MarkItDown | 检查 `.env` 中 `MINERU_MODE` 是否为 `local`，并确认本地 `mineru-api` 服务真实可达；仅修改这个变量不会自动启用本地 MinerU |
| Cloud 模式无法处理 PDF | 检查 `.env` 中 `MINERU_API_KEY` 是否已填写 |
| 默认模式下没有 `mineru-api` 容器 | 这是正常现象；默认模式使用云端 MinerU，只有 GPU 覆盖栈才会启动本地 `mineru-api` |
| `docker compose down -v` 后文档丢失 | 默认 Docker 模式的文档在 MinIO volume 中，执行该命令会一并删除 |
| Windows curl 上传文件名乱码 | 使用 `python scripts/upload_documents.py` 代替 curl |

---
