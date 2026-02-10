# Improve-5 实施报告

## 1. 实施范围

本次落地覆盖 Improve-5 的核心三项：

1. MinerU 熔断策略改为“连续失败阈值触发”。
2. `processing` 子阶段状态机落地（含 ES/Embedding 可观测性）。
3. PDF 兜底链路从 PyPDF 切换为 MarkItDown。

---

## 2. 关键实现

## 2.1 熔断与超时策略

实现结果：

1. 熔断从“单次失败立刻 cooldown”改为“连续失败 5 次触发 cooldown”。
2. 配置项简化并统一：
   - `MINERU_V4_TIMEOUT`（默认 120）
   - `MINERU_FAIL_THRESHOLD`（默认 5）
   - `MINERU_COOLDOWN_SECONDS`（默认 120）
3. MinerU Cloud API 请求采用固定 connect timeout + 统一 read timeout；上传/下载沿用大文件保护读超时。

涉及文件：

1. `medimind_agent/infrastructure/document_processing/processor.py`
2. `medimind_agent/infrastructure/document_processing/converters/mineru_cloud_converter.py`
3. `medimind_agent/configs/document_processing.yaml`
4. `.env.example`
5. `docker-compose.yml`

## 2.2 processing 子阶段状态机

实现结果：

1. 文档模型新增字段：
   - `processing_stage`
   - `stage_updated_at`
   - `processing_meta`
2. Worker 处理过程按阶段落库并提交：
   - `converting`
   - `splitting`
   - `embedding`
   - `indexing_pg`
   - `indexing_es`
   - `finalizing`
3. 失败时写回失败阶段与错误信息，便于定位。
4. 增加索引补偿清理：索引阶段失败时触发节点清理，减少“部分写入”脏数据风险。
5. API 响应已透出阶段字段，前端可直接轮询展示“正在处理 + 当前阶段”。

涉及文件：

1. `medimind_agent/domain/entities/document.py`
2. `medimind_agent/domain/repositories/document_repository.py`
3. `medimind_agent/infrastructure/persistence/models.py`
4. `medimind_agent/infrastructure/persistence/repositories/document_repo_impl.py`
5. `medimind_agent/infrastructure/persistence/database.py`
6. `medimind_agent/infrastructure/tasks/document_tasks.py`
7. `medimind_agent/api/models/responses.py`
8. `medimind_agent/api/routers/documents.py`
9. `medimind_agent/api/routers/library.py`
10. `medimind_agent/api/routers/notebook_documents.py`
11. `medimind_agent/scripts/db/init-postgres.sql`

## 2.3 PDF 兜底改为 MarkItDown

实现结果：

1. `MarkItDownConverter` 新增 `.pdf` 支持。
2. 默认链路调整为：`MinerU -> MarkItDown`。
3. 加入 PDF 依赖预检查（`pdfminer.six`）与缺失时显式错误。

涉及文件：

1. `medimind_agent/infrastructure/document_processing/converters/markitdown_converter.py`
2. `medimind_agent/infrastructure/document_processing/processor.py`
3. `medimind_agent/infrastructure/document_processing/converters/__init__.py`

## 2.4 四模式 notebook 作用域收敛与日志降噪

实现结果：

1. `chat` 模式 source 收集补齐 `allowed_doc_ids` 后过滤。
2. `conclude` 模式引入 scoped retriever，确保总结上下文仅来自 notebook 文档。
3. Chat ES tool 支持 notebook 作用域（查询预过滤 + 结果后过滤）。
4. `ChatMode` 在作用域变化时刷新工具实例，避免旧作用域污染。
5. `ChatService` 缺失文档 source 告警改为按 doc_id 聚合输出。
6. `AskMode` 增加空召回兜底：首轮无命中时基于 notebook 文档标题做一次增强查询重试（不放宽作用域）。

涉及文件：

1. `medimind_agent/core/engine/modes/chat_mode.py`
2. `medimind_agent/core/engine/modes/conclude_mode.py`
3. `medimind_agent/core/rag/retrieval/scoped_retriever.py`
4. `medimind_agent/core/tools/tool_registry.py`
5. `medimind_agent/core/tools/es_search_tool.py`
6. `medimind_agent/application/services/chat_service.py`
7. `medimind_agent/tests/unit/test_scoped_retriever.py`
8. `medimind_agent/tests/unit/test_modes.py`
9. `medimind_agent/tests/unit/test_tools.py`
10. `medimind_agent/tests/unit/test_chat_service_guards.py`
11. `medimind_agent/core/engine/modes/ask_mode.py`
12. `medimind_agent/tests/unit/test_modes.py`

---

## 3. 兼容性与迁移

1. 通过 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 实现运行时兼容，支持历史卷渐进升级。
2. 初始化 SQL 同步新增字段，保证新部署与旧升级路径一致。
3. API 字段新增为向后兼容（均为可选字段），不破坏旧客户端解析。

---

## 4. 结构化错误语义补充

1. 文档内容读取在文档未完成时会返回结构化 `E4001`（`409`），避免 500。
2. 该行为与 improve-4 建立的统一异常处理链路保持一致。
