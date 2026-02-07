# 🚀 MediMind Agent 快速开始

## 📦 安装依赖

### 1. 安装 uv（推荐的依赖管理工具）

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

## ⚙️ 配置环境变量

```bash
# 复制环境配置模板
cp .env.example .env

# 编辑 .env 文件，配置必需项：
# - ZHIPU_API_KEY: 智谱AI API密钥
# - POSTGRES_PASSWORD: 数据库密码
# - 其他配置保持默认即可
```

## 🐳 启动后端服务（Docker）

### CPU 模式（无需 GPU）

```bash
# 启动所有后端服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

启动的服务包括：
- ✅ Redis（端口 6379）
- ✅ PostgreSQL + pgvector（端口 5432）
- ✅ Elasticsearch（端口 9200）
- ✅ MinerU API CPU 版（端口 8001）
- ✅ Celery Worker（异步任务处理）

### GPU 模式（需要 NVIDIA GPU + nvidia-container-toolkit）

```bash
# 使用 GPU 配置启动
docker-compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build

# 或使用便捷脚本（自动检测 GPU）
.\scripts\up-mineru.ps1
```

### 仅启动核心服务（不启动监控工具）

```bash
docker-compose up -d redis postgres elasticsearch mineru-api celery-worker
```

## 🌐 启动 FastAPI 应用

```bash
# 确保虚拟环境已激活
python -m uvicorn medimind_agent.api.main:app --reload --port 8000
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

# 测试 MinerU API
curl http://localhost:8001/docs

# 测试 Elasticsearch
curl http://localhost:9200
```

### 2. 测试 FastAPI

```bash
# 健康检查
curl http://localhost:8000/health

# 查看 API 文档
# 浏览器访问：http://localhost:8000/docs
```

## 🎯 常用命令

### Docker 管理

```bash
# 停止所有服务
docker-compose down

# 重启特定服务
docker-compose restart mineru-api

# 查看实时日志
docker-compose logs -f celery-worker

# 清理并重启（会删除数据！）
docker-compose down -v && docker-compose up -d
```

### FastAPI 开发

```bash
# 开发模式（自动重载）
python -m uvicorn medimind_agent.api.main:app --reload --port 8000

# 生产模式
python -m uvicorn medimind_agent.api.main:app --host 0.0.0.0 --port 8000

# 指定 workers（生产环境）
python -m uvicorn medimind_agent.api.main:app --host 0.0.0.0 --port 8000 --workers 4
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
python scripts/rebuild_pgvector.py

# 构建 Elasticsearch 索引
python scripts/rebuild_es.py
```

将文档放在 `data/documents/` 目录下（按类型分类：pdf/、md/、txt/ 等）。

## 🎉 完成！

现在你可以：
1. 访问 API 文档：http://localhost:8000/docs
2. 使用 Postman 测试接口（参考 `postman_collection.json`）
3. 查看详细文档：`docs/` 目录

---

**常见问题**

- ❓ **端口冲突**：修改 `docker-compose.yml` 中的端口映射
- ❓ **依赖安装失败**：尝试 `uv sync --reinstall`
- ❓ **Docker 服务启动慢**：首次启动需要下载镜像和模型，请耐心等待
- ❓ **GPU 不可用**：确保安装了 nvidia-container-toolkit，或使用 CPU 模式

需要帮助？查看 `README.md` 或项目文档。
