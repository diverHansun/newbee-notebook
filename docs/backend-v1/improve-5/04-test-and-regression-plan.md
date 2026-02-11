# Improve-5 测试与回归计划

## 1. 测试目标

1. 验证熔断从“单次失败”升级为“连续失败阈值触发”。
2. 验证 `processing` 子阶段在 API 轮询中可见。
3. 验证 PDF 降级链路由 MarkItDown 接管。
4. 验证本地与容器依赖差异可被快速识别。

## 2. 单元测试

## 2.1 熔断与超时

1. 连续失败计数累加与重置逻辑。
2. 第 5 次失败后触发 cooldown。
3. cooldown 期间跳过 MinerU。
4. cooldown 后成功请求恢复闭合状态。

建议文件：

1. `newbee_notebook/tests/unit/test_document_processing_processor.py`
2. `newbee_notebook/tests/unit/test_mineru_cloud_converter.py`（如已存在则扩展）

## 2.2 状态机子阶段

1. 进入 `processing` 后按阶段写入 `processing_stage`。
2. Embedding 失败时阶段与错误消息一致。
3. ES 失败时阶段与补偿清理逻辑触发。
4. 成功后 `status=completed` 与阶段收敛。

建议文件：

1. `newbee_notebook/tests/unit/test_document_tasks_stage_transitions.py`（新增）

## 2.3 PDF 兜底链路

1. MinerU 失败时触发 MarkItDown PDF 兜底。
2. MarkItDown 缺失 PDF 依赖时抛出可识别错误。
3. 非 PDF 文件不受本次调整影响。

建议文件：

1. `newbee_notebook/tests/unit/test_markitdown_pdf_fallback.py`（新增）

## 2.4 Notebook 作用域收敛

1. `chat` 模式 source 仅包含 notebook 内 document_id。
2. `conclude` 模式检索上下文仅来自 notebook 文档。
3. Chat ES tool 开启作用域后不返回 notebook 外文档。
4. 缺失 document source 告警按 doc_id 聚合（单次请求仅一次）。

建议文件：

1. `newbee_notebook/tests/unit/test_scoped_retriever.py`
2. `newbee_notebook/tests/unit/test_modes.py`
3. `newbee_notebook/tests/unit/test_tools.py`
4. `newbee_notebook/tests/unit/test_chat_service_guards.py`

---

## 3. 集成测试

## 3.1 核心流程

1. 上传 PDF -> 关联 Notebook -> 触发处理 -> 轮询状态 -> Chat ask/explain/conclude。
2. 验证处理中阶段推进可观察。
3. 验证完成后 RAG 正常返回。

## 3.2 失败注入

1. 模拟 MinerU 接口超时（前 4 次失败）：不熔断。
2. 第 5 次失败：触发熔断并转降级。
3. 模拟 embedding 或 ES 异常：状态停在对应阶段并失败收敛。

## 3.3 扫描件专项

1. 云端 MinerU 可用：扫描件应优先走 MinerU。
2. 云端不可用：验证降级效果并记录能力边界。
3. 文档中明确建议 GPU 本地 MinerU OCR。

---

## 4. 依赖一致性检查

## 4.1 本地 `.venv`

检查项：

1. `markitdown` 版本
2. `pdfminer` 可导入
3. `MarkItDown().convert(pdf)` 可执行

## 4.2 docker `celery-worker`

检查项：

1. 容器内 `markitdown` 与 PDF 依赖可导入
2. 文档处理实际由容器执行，结果与本地预期一致

判定原则：

1. 以容器运行结果为准。
2. 本地结果用于快速开发反馈，不替代容器验证。

---

## 5. 回归检查（对照 improve-1 ~ improve-4）

1. `E4001` 响应契约不回退。
2. `pending -> processing -> completed/failed` 主状态语义不回退。
3. Notebook/Session/Library API 兼容性不回退。
4. `postman_collection.json` 断言更新为新阶段字段（如新增对外返回）。
5. docker 相关配置与启动方式与文档保持一致。
6. `postman_collection.json` 包含 `DELETE /library/documents/{document_id}` 用例并通过。

---

## 6. 发布门禁

1. 单元测试通过。
2. 集成测试通过（至少覆盖一份大 PDF 与一份扫描件样本）。
3. `postman_collection.json` 已同步。
4. `docs/backend-v1/improve-5` 文档与实现一致。
5. 关键日志字段可用于排障（阶段、熔断计数、错误码）。
