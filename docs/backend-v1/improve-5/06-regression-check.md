# Improve-5 回归检验（对照 improve-1 ~ improve-4）

## 1. 检验目标

确认 Improve-5 实施后：

1. 不破坏 improve-1 的 Library-first 流程与主状态机语义。
2. 不破坏 improve-2 的 MinerU 三模式接入与 Docker 运行边界。
3. 延续 improve-3/4 的错误语义修复结果（尤其 `E4001` 结构化响应）。
4. 在以上基础上新增可观测子阶段与更稳健熔断策略。
5. 四模式 RAG/ES 检索作用域保持 notebook 一致性，不回退到全局检索。

---

## 2. 对照范围

1. `docs/backend-v1/improve-1/README.md`
2. `docs/backend-v1/improve-2/README.md`
3. `docs/backend-v1/improve-3/test-report.md`
4. `docs/backend-v1/improve-4/04-regression-check.md`
5. `docs/ai-core-v1/08-error-handling.md`

---

## 3. 回归结果

## 3.1 improve-1（Library-first 与状态流）

结论：保持兼容。

1. 上传仍为 `uploaded`，不自动处理。
2. Notebook 关联仍触发 `pending` 入队。
3. 主状态链保持：`uploaded -> pending -> processing -> completed/failed`。
4. 新增字段仅增强可观测性，不改变主状态判断逻辑。

## 3.2 improve-2（MinerU 三模式与容器运行边界）

结论：保持兼容并增强稳定性。

1. cloud/local 模式分支不变。
2. 熔断策略从“单次失败”调整为“连续失败阈值”。
3. `MINERU_FAIL_THRESHOLD`/`MINERU_COOLDOWN_SECONDS` 已注入 `celery-worker` 环境变量。
4. 处理主体仍在 worker 容器，符合 improve-2 运行约束。

## 3.3 improve-3/4（错误码与处理中可见性）

结论：延续并增强。

1. `E4001` 结构化响应链路保持有效。
2. 处理状态不仅可见 `processing`，还可见内部阶段（`processing_stage`）。
3. 失败时记录失败阶段，定位颗粒度提升。

## 3.4 作用域一致性（improve-5 补充）

结论：已补齐。

1. `ask/explain` 延续 `HybridRetriever + allowed_doc_ids` 后过滤。
2. `chat` 的 source 收集链路补充 notebook 后过滤。
3. `conclude` 改为 scoped retriever，检索上下文仅来自 notebook 文档。
4. Chat ES tool 增加 notebook 作用域（预过滤 + 后过滤双保险）。

---

## 4. 测试执行结果

执行命令：

1. `.\\.venv\\Scripts\\python.exe -m pytest -q medimind_agent/tests/unit/test_document_processing_processor.py medimind_agent/tests/unit/test_document_service_content_guard.py medimind_agent/tests/unit/test_chat_service_guards.py medimind_agent/tests/unit/test_delete_document_nodes_task.py`
2. `.\\.venv\\Scripts\\python.exe -m pytest -q medimind_agent/tests/unit`
3. `python -m json.tool postman_collection.json`

结果：

1. 定向回归测试通过（14/14）。
2. 全量 unit 仍有既有基线失败 3 项（`test_selector.py`，`SessionManager` 构造签名历史不一致），与本次改动无直接关联。
3. `postman_collection.json` 语法校验通过。

---

## 5. Postman 与 Docker 检查结论

1. `docker-compose.yml` 已同步 improve-5 新环境变量与默认值。
2. `postman_collection.json` 已补充 `DELETE /library/documents/{document_id}?force=true` 用例。
3. Notebook 取消关联与 Library 删除文档语义在集合中均有覆盖，不冲突。

---

## 6. 残余风险

1. 子阶段需要结合真实大文档压力测试观察轮询粒度是否满足前端体验（尤其 `embedding` 阶段停留时长）。
2. 历史数据库若权限受限可能导致运行时 `ALTER TABLE` 无法执行，需要手动执行初始化 SQL 中的 backfill 语句。
3. `test_selector.py` 的既有失败建议单独立项修复，避免影响未来 CI 基线。
