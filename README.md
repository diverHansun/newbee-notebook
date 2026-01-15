# 🧠 MediMind Agent

多模式智能助手，支持 Chat / Ask / Conclude / Explain，带会话记忆与持久化，可调用 Tavily 搜索、Elasticsearch BM25，以及 RAG（pgvector+ES）。

## ✨ 功能概览

- 💬 **Chat**：自由对话，可用 Tavily（搜索/新闻/抓取）和 ES 工具
- ❓ **Ask**：RAG 深度问答，混合检索（pgvector+ES），ReAct agent
- 📝 **Conclude**：文档总结，支持独立记忆
- 📚 **Explain**：概念讲解，基于向量检索
- 🔄 **会话管理**：`/history`、`/session list`、`/resume`、`/delete`、`/status`、`/reset`

## 🚀 快速开始

### 1️⃣ 安装依赖（推荐 uv）
```bash
pip install uv
uv sync
.venv\Scripts\activate
```
或使用传统方式：
```bash
pip install -r requirements.txt
```

### 2️⃣ 配置环境
```bash
cp .env.example .env
```
设置至少：
- `OPENAI_API_KEY` 或 `ZHIPU_API_KEY`（Zhipu OpenAI 兼容接口）
- `ELASTICSEARCH_URL`（如 `http://localhost:9200`）
- PG 连接（用于 pgvector / 会话持久化）

### 3️⃣ 启动
```bash
python main.py
```

**常用命令**：`/mode <chat|ask|conclude|explain>`、`/history [n]`、`/session list`、`/resume <id>`、`/delete <id>`、`/reset`、`/status`

## 📊 数据与索引

- 📁 文档放在 `data/documents/`（按类型分目录）
- 🔨 向量/ES 建索引：使用 `scripts/rebuild_pgvector.py` 和 `scripts/rebuild_es.py`（需运行 PG+ES）

💡 **提示**：使用 `docker-compose up -d` 可快速启动 PostgreSQL 和 Elasticsearch 服务

## ⚙️ 配置

- `configs/llm.yaml` - LLM 模型参数（Zhipu OpenAI 兼容接口）
- `configs/embeddings.yaml` - 嵌入模型配置（Zhipu/BioBERT）
- `configs/memory.yaml` - 会话记忆配置（Token 限制、摘要提示词）
- `configs/modes.yaml` - 模式参数（Chat/Ask/Conclude/Explain）
- `configs/rag.yaml` - RAG 检索配置（Top-K、相关性阈值、重排序等）
- `configs/storage.yaml` - 存储配置（PostgreSQL/pgvector/Elasticsearch/会话存储）

