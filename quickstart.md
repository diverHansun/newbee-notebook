# 🚀 Newbee Notebook 快速开始

## 📦 安装依赖

### 1. 安装 uv（推荐）

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

或使用 pip 安装：
```bash
pip install uv
```

### 2. 同步项目依赖

```bash
# 使用 uv 安装所有依赖（自动创建虚拟环境）
uv sync

# 激活虚拟环境
# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 3. 可选：本地 Embedding GPU 加速

- 若你使用本地 embedding 模型且机器有独立 GPU，可按 PyTorch 官方指引安装与本机 CUDA 匹配的 `torch` 版本：
  https://pytorch.org/get-started/locally/
- 若主要使用云端 embedding API，则不需要本机 GPU。

可用以下命令检查当前 `torch` 是否启用 CUDA：

```bash
python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available())"
```

## ⚙️ 配置环境变量

```bash
# 复制环境配置模板
cp .env.example .env

# 编辑 .env 文件，配置必需项：
# - ZHIPU_API_KEY: 智谱 AI API 密钥
# - POSTGRES_PASSWORD: 数据库密码
# - MINERU_MODE: cloud 或 local
# - MINERU_API_KEY: cloud 模式必填
```

MinerU 推荐配置（cloud 模式）：

```bash
MINERU_ENABLED=true
MINERU_MODE=cloud
MINERU_API_KEY=
MINERU_V4_API_BASE=https://mineru.net
MINERU_V4_TIMEOUT=60
MINERU_V4_POLL_INTERVAL=5
MINERU_V4_MAX_WAIT_SECONDS=1800
```

本地 CPU 模式（可选）：

```bash
MINERU_MODE=local
MINERU_LOCAL_API_URL=http://mineru-api:8000
MINERU_BACKEND=pipeline
MINERU_LANG_LIST=ch,en
MINERU_LOCAL_TIMEOUT=0
```

本地 GPU 模式（可选）：

```bash
MINERU_MODE=local
MINERU_LOCAL_API_URL=http://mineru-api:8000
MINERU_BACKEND=hybrid-auto-engine
MINERU_LANG_LIST=ch,en
MINERU_LOCAL_TIMEOUT=0
```

文件处理策略（当前）：
- PDF：`MinerU (cloud/local) -> PyPdf fallback`
- CSV / Word / TXT / MD / HTML 等：`MarkItDown -> Markdown`
- 存储目录：`data/documents/{document_id}/...`（不再使用 `data/documents/pdf|txt|word...` 分类目录）

## 🐳 启动后端服务（Docker）

### 默认模式（推荐：cloud，不启动 mineru-api）

```bash
# 启动基础后端服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

默认启动服务包括：
- ✅ Redis（端口 6379）
- ✅ PostgreSQL + pgvector（端口 5432）
- ✅ Elasticsearch（端口 9200）
- ✅ Celery Worker（异步任务处理）

### 本地 CPU 模式（启用 mineru-api）

```bash
docker-compose --profile mineru-local up -d --build
```

### 本地 GPU 模式（需要 NVIDIA GPU + nvidia-container-toolkit）

```bash
# 使用 GPU 配置 + local profile 启动
docker-compose -f docker-compose.yml -f docker-compose.gpu.yml --profile mineru-local up -d --build

# 或使用便捷脚本（自动检测 GPU）
.\scripts\up-mineru.ps1
```

说明：
- 当使用 `docker-compose.gpu.yml` 时，worker 默认使用 `MINERU_BACKEND=hybrid-auto-engine`（可在 `.env` 覆盖）。
- 建议同时配置 `MINERU_MODE=local`，确保 PDF 走本地 MinerU 服务。
- 如果 `.env` 中已明确写了 `MINERU_MODE=cloud`，请改回 `local` 再启动本地模式。

### 仅启动核心服务（手动指定）

```bash
docker-compose up -d redis postgres elasticsearch celery-worker
```

## 🌐 启动 FastAPI 应用

```bash
# 确保虚拟环境已激活
python -m uvicorn newbee_notebook.api.main:app --reload --port 8000
```

启动成功后访问：
- 📖 API 文档：http://localhost:8000/docs
- 📊 ReDoc 文档：http://localhost:8000/redoc
- 🔍 健康检查：http://localhost:8000/health

## ✅ 验证服务

### 1. 检查 Docker 服务

```bash
# 查看所有容器状态
docker-compose ps

# 测试 Elasticsearch
curl http://localhost:9200
```

如果你使用的是本地 MinerU 模式，再额外验证：

```bash
curl http://localhost:8001/docs
```

### 2. 测试 FastAPI

```bash
# 健康检查
curl http://localhost:8000/health

# 查看 API 文档
# 浏览器访问：http://localhost:8000/docs
```

### 3. 推荐上传方式（避免 Windows `curl` 文件名乱码）

```bash
# 上传一个或多个文件（支持中文 Windows 路径）
python scripts/upload_documents.py "D:\docs\中文病例.pdf"
python scripts/upload_documents.py "D:\docs\中文病例.pdf" "D:\docs\检验结果.docx"
```

说明：
- 脚本基于 `requests`，默认对 multipart 文件名做 UTF-8 编码处理。
- 服务端会自动还原文件名，减少命令行编码导致的乱码问题。
- 脚本分层规范见 `scripts/README.md`。

## 🎯 常用命令

### Docker 管理

```bash
# 停止所有服务
docker-compose down

# 重启特定服务
docker-compose restart mineru-api

# 查看实时日志
docker-compose logs -f celery-worker

# 清理并重启（会删除 Docker volumes 中的数据）
docker-compose down -v
docker-compose up -d

# 注意：down -v 不会删除宿主机 data/documents 目录中的文件
# 如需清理孤儿目录（推荐）
make clean-orphans

# 或按 document_id 精确删除
make clean-doc ID=<document_id>
# Windows PowerShell:
# .\scripts\clean-doc.ps1 -Id <document_id>
```

说明：
- `mineru-api` 只有在 `--profile mineru-local` 启动后才会存在。
- cloud 模式通常不需要 `restart mineru-api`。
- 应用启动时会检测 `data/documents` 中的孤儿目录并输出日志告警，不会自动删除。

### FastAPI 开发

```bash
# 开发模式（自动重载）
python -m uvicorn newbee_notebook.api.main:app --reload --port 8000

# 生产模式
python -m uvicorn newbee_notebook.api.main:app --host 0.0.0.0 --port 8000

# 指定 workers（生产环境）
python -m uvicorn newbee_notebook.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 🛠️ 可选：启动监控工具

```bash
# 启动 Celery 监控（Flower）
docker-compose --profile monitor up -d flower
# 访问：http://localhost:5555

# 启动 Elasticsearch 可视化（Kibana）
docker-compose --profile debug up -d kibana
# 访问：http://localhost:5601
```

## 📊 初始化数据索引（可选）

如果需要使用 RAG 功能，需要先构建索引：

```bash
# 构建 pgvector 索引
python -m newbee_notebook.scripts.rebuild_pgvector

# 构建 Elasticsearch 索引
python -m newbee_notebook.scripts.rebuild_es
```

说明：
- 后端脚本建议统一通过 `python -m newbee_notebook.scripts.<name>` 调用。
- `scripts/` 目录保留全局入口与用户直接运行脚本。

## 🎉 完成

现在你可以：
1. 访问 API 文档：http://localhost:8000/docs
2. 使用 Postman 测试接口（参考 `postman_collection.json`）
3. 查看详细文档：`docs/` 目录

---

**常见问题**

- ❓ **端口冲突**：修改 `docker-compose.yml` 中的端口映射
- ❓ **依赖安装失败**：尝试 `uv sync --reinstall`
- ❓ **Docker 服务启动慢**：本地 MinerU 首次启动需要下载模型，请耐心等待
- ❓ **GPU 不可用**：确保安装了 nvidia-container-toolkit，或使用 CPU 模式
- ❓ **本地模式仍走云端**：检查 `.env` 中 `MINERU_MODE` 是否为 `local`
- ❓ **cloud 模式无法处理 PDF**：检查 `.env` 中 `MINERU_API_KEY` 是否已填写

需要帮助？查看 `README.md` 或项目文档。
