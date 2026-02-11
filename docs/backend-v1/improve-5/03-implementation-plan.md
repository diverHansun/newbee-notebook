# Improve-5 实施计划

## 1. 实施目标

1. 实现“连续失败 5 次再熔断”的 MinerU 可用性策略。
2. 在 `processing` 内部增加可观测子阶段，覆盖 ES/Embedding 关键过程。
3. PDF 降级路径从 PyPDF 切换为 MarkItDown。
4. 完成本地与容器依赖一致性治理。

## 2. 任务拆分

## 2.1 任务 A：熔断与超时策略改造（P0）

目标：提高瞬时网络抖动容忍度，避免过长误熔断。

实施项：

1. 在 `DocumentProcessor` 中增加连续失败计数与阈值判断。
2. 仅当计数达到阈值时进入 cooldown。
3. 成功请求后重置失败计数。
4. 超时策略改为固定 connect + 简化 read timeout。
5. 更新配置项与默认值文档。

涉及文件（计划）：

1. `newbee_notebook/infrastructure/document_processing/processor.py`
2. `newbee_notebook/infrastructure/document_processing/converters/mineru_cloud_converter.py`
3. `newbee_notebook/configs/document_processing.yaml`
4. `.env.example`

验收标准：

1. 连续 1~4 次失败不熔断。
2. 第 5 次失败触发熔断并进入 cooldown。
3. cooldown 后首次成功可自动恢复闭合状态。

---

## 2.2 任务 B：`processing` 子阶段状态机（P0）

目标：让 ES/Embedding 卡点可见、可定位、可回归。

实施项：

1. 扩展 `documents` 表字段：`processing_stage`、`stage_updated_at`、`processing_meta`（可选）。
2. 扩展 ORM 模型与 Repository 更新方法。
3. 在 `_process_document_async` 中按阶段落库并提交：
   - converting
   - splitting
   - embedding
   - indexing_pg
   - indexing_es
   - finalizing
4. 失败路径记录失败阶段。
5. 补充索引失败补偿清理逻辑。

涉及文件（计划）：

1. `newbee_notebook/scripts/db/init-postgres.sql`
2. `newbee_notebook/infrastructure/persistence/models.py`
3. `newbee_notebook/infrastructure/persistence/repositories/document_repo_impl.py`
4. `newbee_notebook/infrastructure/tasks/document_tasks.py`
5. `newbee_notebook/api/models/responses.py`
6. `newbee_notebook/api/routers/documents.py`
7. `newbee_notebook/api/routers/notebook_documents.py`

验收标准：

1. API 轮询可见阶段推进。
2. Embedding/ES 任一失败时，`processing_stage` 能准确标识失败点。
3. `completed` 后阶段字段一致收敛。

---

## 2.3 任务 C：PDF 兜底切换 MarkItDown（P0）

目标：提升 MinerU 不可用时 PDF 降级链路的结构化能力。

实施项：

1. `MarkItDownConverter` 增加 `.pdf` 支持。
2. 调整处理器顺序为 `MinerU -> MarkItDown`（PDF）。
3. 将 PyPDF 改为可选兼容或从默认链路移除。
4. 增加 MarkItDown PDF 依赖预检与错误提示。

涉及文件（计划）：

1. `newbee_notebook/infrastructure/document_processing/converters/markitdown_converter.py`
2. `newbee_notebook/infrastructure/document_processing/processor.py`
3. `requirements.txt`
4. `pyproject.toml`

验收标准：

1. MinerU 不可用时，PDF 仍可走 MarkItDown 处理。
2. 缺失 PDF 依赖时，错误信息可读且可定位。

---

## 2.4 任务 D：依赖一致性与环境校验（P1）

目标：避免本地与容器环境行为不一致。

实施项：

1. 新增依赖自检脚本（本地/容器可复用）。
2. 补充文档说明：
   - 本地 `.venv` 如何验证 PDF 依赖
   - docker worker 如何验证运行时依赖
3. 用户指南新增 GPU MinerU 建议与场景边界。

涉及文件（计划）：

1. `scripts/`（新增自检脚本）
2. `docs/backend-v1/improve-5/*`
3. 用户指南文档（后续阶段）

验收标准：

1. 可一条命令判断 PDF 依赖是否就绪。
2. 文档明确本地与容器依赖职责边界。

---

## 2.5 任务 E：四模式 notebook 作用域收敛（P0）

目标：保证 `chat/ask/explain/conclude` 在 RAG/ES 过程中只使用当前 Notebook 文档。

实施项：

1. `chat` 模式 `_collect_sources` 增加 `allowed_doc_ids` 后过滤。
2. `conclude` 模式引入 scoped retriever，统一执行后过滤。
3. Chat ES tool 增加 notebook 作用域（查询预过滤 + 结果后过滤）。
4. `ChatMode` 在作用域变化时刷新工具实例，避免旧作用域污染。
5. `ChatService` 缺失文档告警改为聚合输出，降低日志噪声。

涉及文件（计划）：

1. `newbee_notebook/core/engine/modes/chat_mode.py`
2. `newbee_notebook/core/engine/modes/conclude_mode.py`
3. `newbee_notebook/core/rag/retrieval/scoped_retriever.py`
4. `newbee_notebook/core/tools/es_search_tool.py`
5. `newbee_notebook/core/tools/tool_registry.py`
6. `newbee_notebook/application/services/chat_service.py`
7. `newbee_notebook/tests/unit/*`

验收标准：

1. 四模式检索返回的 source/document_id 均位于 notebook 作用域。
2. Chat ES tool 不再返回 notebook 外文档。
3. 缺失文档 warning 对同一 doc_id 单次请求仅输出一次。

## 3. 实施顺序

1. 先做任务 A（熔断与超时），降低可用性风险。
2. 再做任务 B（子阶段状态机），增强排障与前端可见性。
3. 完成任务 C（MarkItDown PDF 兜底）并跑回归。
4. 做任务 D（依赖校验与文档收敛）。
5. 最后做任务 E（四模式 notebook 作用域收敛）并执行回归。

## 4. 风险与回滚

1. 风险：新增 DB 字段与历史库不兼容。  
缓解：提供 `ALTER TABLE` 升级脚本与默认值。

2. 风险：MarkItDown PDF 在部分扫描件场景表现仍有限。  
缓解：用户指南明确推荐 GPU MinerU OCR，保留可选兼容开关。

3. 风险：状态阶段过多导致日志噪声。  
缓解：统一结构化日志并设置关键级别。

回滚策略：

1. 可通过配置开关回退熔断阈值策略。
2. 可临时恢复 PyPDF 兼容路径（若保留开关）。
3. 子阶段字段不影响主状态语义，可向后兼容读取。
