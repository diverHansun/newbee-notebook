# MediMind Agent 技术概览（当前实现）

## 架构与模式
- 模式：Chat（多工具）、Ask（ReAct + 混合检索）、Conclude（ChatEngine summarization，独立记忆）、Explain（QueryEngine）。
- 工具：Tavily 搜索/新闻/URL 抓取，Elasticsearch BM25。
- 检索：pgvector 语义 + Elasticsearch BM25，RRF 融合（Ask）；Conclude/Explain 走向量检索。
- LLM：Zhipu OpenAI 兼容接口（也可用原生 OpenAI），统一由 `src/llm` 构建。
- 记忆：Chat/Ask 共享 `ChatMemoryBuffer`；Conclude 独立记忆；会话可持久化到 PG。

## 运行与存储
- 数据源：`data/documents/`。
- 索引：`scripts/rebuild_pgvector.py`、`scripts/rebuild_es.py`（依赖 Postgres+pgvector、Elasticsearch）。
- 会话存储：Postgres（`chat_sessions` / `chat_messages`）；命令 `/history` `/session list` `/resume` `/delete`。

## 目录速览
- `src/engine/modes/`：各模式实现。
- `src/tools/`：Tavily/ES 工具。
- `src/infrastructure/session/`：会话持久化。
- `src/prompts/`：模式提示词。
- `configs/`：LLM、embedding、存储、模式配置。

## 使用要点
- 启动：`python main.py`；命令 `/mode <chat|ask|conclude|explain>`、`/history [n]`、`/session list`、`/resume <id>`、`/delete <id>`、`/reset`。
- 环境：OPENAI_API_KEY 或 ZHIPU_API_KEY；ELASTICSEARCH_URL；PG 连接。

## 演进建议
- API 化：用 FastAPI 暴露 4 模式接口，传入/返回 `session_id` 支持恢复。
- 用户隔离：按用户/会话键控内存与存储；连接池/限流配置在 PG/ES/LLM/Tavily。
- 安全：在应用层做鉴权、审计；命令与工具调用日志化；在 LLM 提示词中明确安全边界。
