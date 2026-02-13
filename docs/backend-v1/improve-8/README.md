# Improve-8: 文档处理流水线模块化拆分

## 1. 阶段背景

在 improve-7 完成模型扩展与多供应商支持后，项目在实际压力测试 MinerU (PDF→Markdown 远程转换) 时暴露了一个**架构级问题**：文档处理流水线 (`_process_document_async`) 是一个六阶段不可拆分的单体函数，所有触发入口（notebook 关联 / admin reprocess / admin reindex）都只能执行**完整流水线**（MinerU 转换 + 文本分块 + 向量嵌入 + pgvector 索引 + ES 索引），无法：

1. **单独测试** MinerU / MarkItDown 转换的稳定性和性能
2. **独立执行**已转换文档的 RAG 索引或 ES 索引
3. **跳过已完成阶段**，只补齐缺失的处理步骤
4. **按阶段重试**，而非整体重跑

本阶段目标是将流水线拆分为**可独立触发的模块**，引入 `CONVERTED` 中间状态，并实现 Notebook 关联时的**智能阶段验证**——自动检测文档已完成的阶段，只补齐缺失部分。

## 2. 本阶段已确认决策

1. 新增 `CONVERTED` 文档状态，作为"MinerU/MarkItDown 转换完成，尚未索引"的稳定中间态。
2. 新增 `ProcessingStage` 枚举，替代硬编码的 stage 字符串。
3. 保持现有 6 个处理阶段不变（converting / splitting / embedding / indexing_pg / indexing_es / finalizing），不合并。
4. 拆分 Celery Task 为：`convert_document_task`（仅转换）、`index_document_task`（仅索引）、`process_document_task`（完整流水线，保持向后兼容）。
5. 新增 Admin API 端点：单文档转换、单文档索引、批量转换（支持 document_ids 过滤）。
6. **智能 Notebook 关联**：加入 Notebook 时检测文档状态，UPLOADED/FAILED→完整流水线，CONVERTED→仅索引，COMPLETED→直接关联。
7. 现有 Notebook 关联入口的行为保持向后兼容（UPLOADED 文档加入 Notebook 仍自动触发完整流水线）。

## 3. 设计约束

1. 与 improve-1 ~ improve-7 的 RAG 管线、对话引擎、模型层兼容。
2. 状态机扩展不破坏现有前端对 `uploaded / processing / completed / failed` 状态的依赖。
3. 转换功能覆盖所有文件类型（PDF via MinerU/MarkItDown、DOCX/XLSX/PPTX 等 via MarkItDown），不仅限 PDF。
4. Celery Task 拆分后保持幂等性和原子性原则。
5. 批量操作支持 document_ids 过滤，提供精确控制粒度。
6. 失败回滚和补偿清理机制继续保持。

## 4. 文档索引

| 序号 | 文档 | 职责 |
|------|------|------|
| 01 | [01-problem-analysis.md](./01-problem-analysis.md) | 问题分析：当前单体流水线的局限性和实际痛点 |
| 02 | [02-state-machine-extension.md](./02-state-machine-extension.md) | 状态机扩展：CONVERTED 状态定义、ProcessingStage 枚举、状态转换规则 |
| 03 | [03-pipeline-modularization.md](./03-pipeline-modularization.md) | 流水线模块化：Celery Task 拆分、阶段函数抽取、错误处理策略 |
| 04 | [04-api-endpoints.md](./04-api-endpoints.md) | API 端点设计：新增 Admin 端点的请求/响应规范 |
| 05 | [05-smart-notebook-association.md](./05-smart-notebook-association.md) | 智能关联逻辑：Notebook 关联时的阶段验证与缺失补齐 |
| 06 | [06-implementation-plan.md](./06-implementation-plan.md) | 实施计划：任务拆分、依赖关系、验收标准 |

## 5. 当前状态

- 文档状态: 设计规划阶段
- 创建日期: 2026-02-13
- 阶段版本: v1.0
- 前置依赖: improve-7 已完成
