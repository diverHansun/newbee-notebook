# Improve-8: 文档处理流水线模块化拆分

## 1. 阶段背景

在 improve-7 完成模型扩展与多供应商支持后，项目在实际压力测试 MinerU (PDF->Markdown 远程转换) 时暴露了一个架构级问题：文档处理流水线 (`_process_document_async`) 是一个六阶段不可拆分的单体函数，所有触发入口（notebook 关联 / admin reprocess / admin reindex）都只能执行完整流水线（MinerU 转换 + 文本分块 + 向量嵌入 + pgvector 索引 + ES 索引），无法：

1. 单独测试 MinerU / MarkItDown 转换的稳定性和性能
2. 独立执行已转换文档的 RAG 索引或 ES 索引
3. 跳过已完成阶段，只补齐缺失的处理步骤
4. 按阶段重试，而非整体重跑

本阶段目标是将流水线拆分为可独立触发的模块，引入 `CONVERTED` 中间状态，并实现 Notebook 关联时的智能阶段验证——自动检测文档已完成的阶段，只补齐缺失部分。

## 2. 产品约束

1. 前端用户态始终使用完整流水线流程：文档关联 Notebook 时自动触发"转换 + RAG + ES"，不暴露分段接口给用户。
2. 新增的 Admin 端点（独立转换/独立索引）用于开发调试和运维排查，不作为用户态功能。
3. 分段式状态机的核心价值在于后台可按阶段暂停、继续、重试，逐步引入可控的流水线管理能力。
4. 转换结果直接覆盖，不做版本管理（YAGNI）。

## 3. 本阶段已确认决策

1. 新增 `CONVERTED` 文档状态，作为"MinerU/MarkItDown 转换完成，尚未索引"的稳定中间态。
2. 新增 `ProcessingStage` 枚举，替代硬编码的 stage 字符串，仅包含过程阶段（不含结果状态）。
3. 处理阶段保持 5 个（converting / splitting / indexing_pg / indexing_es / finalizing），移除 embedding（pgvector insert 内部完成，不单独暴露）。
4. 拆分 Celery Task 为：`convert_document_task`（仅转换）、`index_document_task`（仅索引）、`process_document_task`（完整流水线，保持向后兼容）。
5. 抽取 `_execute_pipeline` 高阶函数，消除三个流水线函数中的重复 boilerplate（DRY）。
6. 新增 Admin API 端点：单文档转换、单文档索引、批量转换、批量索引（支持 document_ids 过滤）。
7. 智能 Notebook 关联：加入 Notebook 时检测文档状态，UPLOADED/FAILED->完整流水线，CONVERTED->仅索引，COMPLETED->直接关联。
8. 现有 Notebook 关联入口的行为保持向后兼容（UPLOADED 文档加入 Notebook 仍自动触发完整流水线）。
9. 索引失败后状态为 FAILED（非 CONVERTED），通过 `processing_meta.conversion_preserved` 标记转换产物是否完整。
10. `CONVERTED` 状态文档在对话场景中视为 blocking（未索引不可对话）。
11. `force=true` 的清理逻辑内联到 convert/index task 中执行，避免异步竟态。
12. `PipelineContext` 新增 `original_status` 字段（claim 前记录），智能跳过通过 `ctx.original_status == CONVERTED` 判断，而非 `ctx.document.status`。
13. `_index_to_stores` 统一管理 INDEXING_PG/INDEXING_ES stage 推进和 `indexed_anything` 标记，调用方不重复设置。
14. `_determine_processing_action` 返回三元组 `(action, task_name, force)`，FAILED+content_path 时 `force=True`，确保 `_index_document_async` 的 `claim_processing` 能匹配 FAILED 状态。
15. `_execute_pipeline` 异常处理中，在补偿清理和 `update_status(FAILED)` 之前先执行 `session.rollback()`，防止 pipeline_fn 中未提交的脏数据被一并 commit。
16. 保留 `ProcessingStage.FINALIZING`，在 `set_terminal_status` 前显式调用 `set_stage(FINALIZING)`，为运维提供"索引已完成，正在收尾"的可观测性。
17. `update_status` 的可选参数使用 sentinel 值（`_UNSET = object()`）区分"未传参"和"显式传 None"，确保 `set_terminal_status` 能将 `processing_stage` / `processing_meta` / `error_message` 正确清空为 NULL。

## 4. 设计约束

1. 与 improve-1 ~ improve-7 的 RAG 管线、对话引擎、模型层兼容。
2. 状态机扩展不破坏现有前端对 `uploaded / processing / completed / failed` 状态的依赖。
3. 转换功能覆盖所有文件类型（PDF via MinerU/MarkItDown、DOCX/XLSX/PPTX 等 via MarkItDown），不仅限 PDF。
4. Celery Task 拆分后保持幂等性和原子性原则。
5. 批量操作支持 document_ids 过滤，提供精确控制粒度。
6. 失败回滚和补偿清理机制继续保持。

## 5. 文档索引

| 序号 | 文档 | 职责 |
|------|------|------|
| 01 | [01-problem-analysis.md](./01-problem-analysis.md) | 问题分析：当前单体流水线的局限性和实际痛点 |
| 02 | [02-state-machine-extension.md](./02-state-machine-extension.md) | 状态机扩展：CONVERTED 状态定义、ProcessingStage 枚举、状态转换规则 |
| 03 | [03-pipeline-modularization.md](./03-pipeline-modularization.md) | 流水线模块化：Celery Task 拆分、阶段函数抽取、错误处理策略 |
| 04 | [04-api-endpoints.md](./04-api-endpoints.md) | API 端点设计：新增 Admin 端点的请求/响应规范 |
| 05 | [05-smart-notebook-association.md](./05-smart-notebook-association.md) | 智能关联逻辑：Notebook 关联时的阶段验证与缺失补齐 |
| 06 | [06-implementation-plan.md](./06-implementation-plan.md) | 实施计划：任务拆分、依赖关系、验收标准 |
| 07 | [07-pipeline-executor.md](./07-pipeline-executor.md) | 流水线执行框架：_execute_pipeline 设计与 PipelineContext |
| TR | [test-report.md](./test-report.md) | 后端端点测试报告：52 项 curl E2E 测试结果与 Bug 记录 |

## 6. 当前状态

- 文档状态: 实现完成，端点测试通过
- 创建日期: 2026-02-13
- 最后更新: 2026-02-19
- 阶段版本: v1.2
- 前置依赖: improve-7 已完成
