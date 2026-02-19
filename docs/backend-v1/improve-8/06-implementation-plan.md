# 06 - 实施计划

## 1. 概述

本文档将 Improve-8 的实施拆分为四个阶段，每个阶段包含具体任务、依赖关系和验收标准。

## 2. Phase 1: 基础设施层（Infrastructure）

**目标**：新增值对象和扩展 Document Entity，不改变运行时行为。

| 任务 | 文件 | 说明 |
|------|------|------|
| 1.1 | `domain/value_objects/processing_stage.py` | 新建 ProcessingStage 枚举（仅过程阶段，不含 COMPLETED/CONVERTED/EMBEDDING） |
| 1.2 | `domain/value_objects/document_status.py` | 新增 CONVERTED 状态，添加 `is_blocking` / `is_stable` / `can_start_indexing` 属性 |
| 1.3 | `domain/entities/document.py` | 新增 `is_converted` / `needs_indexing` / `is_ready_for_chat` / `mark_converted()` |
| 1.4 | `infrastructure/persistence/repositories/document_repo_impl.py` | `claim_processing` 支持 CONVERTED 作为源状态；`update_status` 引入 sentinel 值支持显式清空 |

**依赖**：无前置依赖

**验收标准**：
- ProcessingStage 枚举不含 COMPLETED / CONVERTED / EMBEDDING
- DocumentStatus.CONVERTED.is_blocking == True
- claim_processing([CONVERTED]) 可用于索引场景
- `update_status(processing_stage=None)` 能正确写入 NULL（而非跳过更新）
- 现有单元测试通过

## 3. Phase 2: 核心逻辑层（Core）

**目标**：实现流水线执行框架和三个执行入口。

| 任务 | 文件 | 说明 |
|------|------|------|
| 2.1 | `infrastructure/tasks/pipeline_context.py` | 新建 PipelineContext 数据类 |
| 2.2 | `infrastructure/tasks/document_tasks.py` | 抽取 `_execute_pipeline` 高阶函数 |
| 2.3 | `infrastructure/tasks/document_tasks.py` | 实现 `_convert_document_async` |
| 2.4 | `infrastructure/tasks/document_tasks.py` | 实现 `_index_document_async` |
| 2.5 | `infrastructure/tasks/document_tasks.py` | 重构 `_process_document_async`（使用 `_execute_pipeline`） |
| 2.6 | `infrastructure/tasks/document_tasks.py` | 注册新 Celery Task（convert_document, index_document, convert_pending, index_pending） |
| 2.7 | `infrastructure/tasks/document_tasks.py` | 实现批量分发函数（`_convert_pending_async`, `_index_pending_async`） |

**依赖**：Phase 1 完成

**验收标准**：
- `_execute_pipeline` 统一处理 session/claim/stage/error
- PipelineContext 包含 `original_status`（claim 前记录）和 `indexed_anything`（pgvector 写入后设置）
- 三个 async 函数不重复 boilerplate（DRY）
- `_process_document_async` 行为与修改前一致（向后兼容）
- `_do_full_pipeline` 智能跳过使用 `ctx.original_status == CONVERTED` 而非 `ctx.document.status`
- convert_document_task 可单独转换 PDF -> CONVERTED
- index_document_task 可将 CONVERTED 文档索引至 COMPLETED
- force=true 时清理逻辑在 task 内部同步执行
- 批量操作分发独立 task（不嵌套 session）
- `_index_to_stores` 统一管理 INDEXING_PG/INDEXING_ES stage 和 indexed_anything 标记
- `_execute_pipeline` 异常处理先 `session.rollback()` 再补偿清理和 `update_status(FAILED)`
- 三个 pipeline_fn 在 `set_terminal_status` 前均调用 `set_stage(FINALIZING)`

## 4. Phase 3: API 层（API）

**目标**：新增 Admin 端点，修改现有端点，提供调试和运维能力。

| 任务 | 文件 | 说明 |
|------|------|------|
| 3.1 | `api/routers/admin.py` | 新增 POST `/admin/documents/{id}/convert` |
| 3.2 | `api/routers/admin.py` | 新增 POST `/admin/documents/{id}/index` |
| 3.3 | `api/routers/admin.py` | 新增 POST `/admin/convert-pending` |
| 3.4 | `api/routers/admin.py` | 新增 POST `/admin/index-pending` |
| 3.5 | `api/routers/admin.py` | 修改 POST `/admin/documents/{id}/reindex`，支持智能跳过 |
| 3.6 | `api/routers/library.py` | `GET /library/documents` 支持 `status=converted` 过滤 |

**依赖**：Phase 2 完成

**验收标准**：
- Postman 可调用所有新端点
- 状态冲突返回 409 / 400 而非 500
- reindex 支持智能跳过，不单独分派 `delete_document_nodes_task`（清理由 task 内部同步执行）

## 5. Phase 4: 集成层（Integration）

**目标**：实现智能 Notebook 关联和对话 blocking 更新。

| 任务 | 文件 | 说明 |
|------|------|------|
| 4.1 | `application/services/notebook_document_service.py` | 实现 `_determine_processing_action`，更新 `add_documents` |
| 4.2 | `application/services/chat_service.py` | CONVERTED 加入 `blocking_statuses` |
| 4.3 | -- | 端到端测试：上传 -> 关联 -> 对话全流程 |

**依赖**：Phase 2 + Phase 3 完成

**验收标准**：
- UPLOADED 文档关联 Notebook -> full_pipeline
- CONVERTED 文档关联 Notebook -> index_only (force=False)
- COMPLETED 文档关联 Notebook -> none
- FAILED+content_path 文档关联 Notebook -> index_only (**force=True**)
- FAILED 无 content_path 文档关联 Notebook -> full_pipeline
- CONVERTED 文档在对话中视为 blocking
- `_determine_processing_action` 返回三元组 `(action, task_name, force)`
- AddDocumentResult 包含 action 字段

## 6. 依赖关系

```
Phase 1 (基础设施)
    |
    v
Phase 2 (核心逻辑) -----> Phase 3 (API)
    |                         |
    +-------------------------+
                |
                v
          Phase 4 (集成)
```

Phase 3 和 Phase 2 存在时序依赖（API 需要调用 Celery Task），但 API 路由注册可以与 Task 实现并行开发。

## 7. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| _execute_pipeline 引入的抽象增加理解成本 | 中 | 保持函数式设计（non-class），PipelineContext 足够简单，详见 07-pipeline-executor.md |
| 现有 process_document_task 行为变更 | 高 | 重构后保持完全向后兼容，UPLOADED 文档加入 Notebook 的行为不变 |
| CONVERTED 状态对前端的影响 | 低 | 前端如使用 switch/case 需增加 converted 分支，不影响主流程 |
| 批量操作触发大量 Celery Task | 中 | 限制单次批量文档数量（如 200），Celery worker 并发受 pool 配置控制 |

## 8. 回滚方案

如需回滚：

1. Celery Task 名称不冲突（新增 convert_document / index_document），回滚不影响现有 process_document
2. DocumentStatus.CONVERTED 是新增值，回滚后需处理数据库中残留的 `converted` 状态记录
3. 回滚脚本：将所有 `status='converted'` 的记录更新为 `status='uploaded'`

```sql
-- 回滚 SQL
UPDATE documents SET status = 'uploaded' WHERE status = 'converted';
```

## 9. 测试策略

### 9.1 单元测试

- ProcessingStage 枚举属性测试
- DocumentStatus 扩展属性测试（is_blocking, can_start_indexing 等）
- `_determine_processing_action` 决策矩阵覆盖

### 9.2 集成测试

- `_execute_pipeline` + 模拟 pipeline_fn 的 session/commit/rollback 行为
- convert_document_task 端到端（Mock MinerU）
- index_document_task 端到端（Mock pgvector/ES）
- process_document_task 的向后兼容验证

### 9.3 端到端测试

- 上传 PDF -> 关联到 Notebook -> 自动对话（验证完整流水线）
- Admin 调用 convert -> 验证 CONVERTED -> 关联到 Notebook -> 自动触发 index_only -> 对话
- Admin 调用 convert-pending + index-pending 批量流程
- force=true 的重转换 / 重索引流程
