# 06 - 实施计划：任务拆分、依赖关系与验收标准

## 1. 实施阶段

本次改进分为 **4 个阶段**，每个阶段可独立验证：

```
Phase 1: 基础设施层（状态机 + 枚举）
    ↓
Phase 2: 核心层（Celery Task 拆分）
    ↓
Phase 3: API 层（新端点 + 现有端点增强）
    ↓
Phase 4: 集成层（智能关联 + 测试）
```

## 2. 任务清单

### Phase 1: 基础设施层 — 状态机与枚举

| # | 任务 | 文件 | 依赖 |
|---|------|------|------|
| 1.1 | 新增 `ProcessingStage` 枚举 | `domain/value_objects/processing_stage.py` | 无 |
| 1.2 | `DocumentStatus` 新增 `CONVERTED` | `domain/value_objects/document_status.py` | 无 |
| 1.3 | `Document` Entity 新增属性方法 | `domain/entities/document.py` | 1.1, 1.2 |
| 1.4 | `DocumentRepositoryImpl.claim_processing()` 支持 `from_statuses` 参数化 | `infrastructure/persistence/repositories/document_repo_impl.py` | 1.2 |
| 1.5 | 验证 DB schema 兼容性（VARCHAR 类型无需迁移） | — | 1.2 |

**验收标准**：
- [ ] `ProcessingStage` 枚举可正确序列化为字符串
- [ ] `DocumentStatus.CONVERTED` 可正常写入和读取数据库
- [ ] `document.is_converted`, `needs_conversion`, `needs_indexing` 属性正确
- [ ] `claim_processing(from_statuses=[CONVERTED])` 可从 CONVERTED 状态认领

### Phase 2: 核心层 — Celery Task 拆分

| # | 任务 | 文件 | 依赖 |
|---|------|------|------|
| 2.1 | 抽取 `_resolve_source_path()` 公共函数 | `infrastructure/tasks/document_tasks.py` | 无 |
| 2.2 | 实现 `_convert_document_async()` | `infrastructure/tasks/document_tasks.py` | 1.1-1.4 |
| 2.3 | 注册 `convert_document_task` Celery Task | `infrastructure/tasks/document_tasks.py` | 2.2 |
| 2.4 | 实现 `_index_document_async()` | `infrastructure/tasks/document_tasks.py` | 1.1-1.4 |
| 2.5 | 注册 `index_document_task` Celery Task | `infrastructure/tasks/document_tasks.py` | 2.4 |
| 2.6 | 重构 `_process_document_async()` 支持智能阶段检测 | `infrastructure/tasks/document_tasks.py` | 2.2, 2.4 |
| 2.7 | 实现 `_convert_pending_async()` 批量转换辅助函数 | `infrastructure/tasks/document_tasks.py` | 2.2 |
| 2.8 | 注册 `convert_pending_task` Celery Task | `infrastructure/tasks/document_tasks.py` | 2.7 |
| 2.9 | 替换所有硬编码 stage 字符串为 `ProcessingStage` 枚举 | `infrastructure/tasks/document_tasks.py` | 1.1 |

**验收标准**：
- [ ] `convert_document_task` 可独立执行，完成后状态为 CONVERTED
- [ ] `index_document_task` 可对 CONVERTED 文档执行，完成后状态为 COMPLETED
- [ ] `process_document_task` 行为与改动前完全一致（回归测试通过）
- [ ] `process_document_task` 对 CONVERTED 文档自动跳过转换阶段
- [ ] 转换失败 → FAILED，不触发向量清理
- [ ] 索引失败 → FAILED，保留磁盘转换产物
- [ ] 批量转换支持 document_ids 过滤
- [ ] 所有 Task 满足幂等性要求

### Phase 3: API 层 — 新端点与增强

| # | 任务 | 文件 | 依赖 |
|---|------|------|------|
| 3.1 | 新增 Request/Response Pydantic Models | `api/models.py` | 无 |
| 3.2 | 实现 `POST /admin/documents/{id}/convert` | `api/routers/admin.py` | 2.3, 3.1 |
| 3.3 | 实现 `POST /admin/documents/{id}/index` | `api/routers/admin.py` | 2.5, 3.1 |
| 3.4 | 实现 `POST /admin/convert-pending` | `api/routers/admin.py` | 2.8, 3.1 |
| 3.5 | `GET /library/documents` 支持 `status=converted` 过滤 | 已自动支持（枚举扩展） | 1.2 |
| 3.6 | `GET /admin/index-stats` 增加 converted 计数 | `api/routers/admin.py` | 1.2 |
| 3.7 | 更新 Postman Collection | `postman_collection.json` | 3.2-3.4 |

**验收标准**：
- [ ] `POST /admin/documents/{id}/convert` 返回 202，后台开始转换
- [ ] `POST /admin/documents/{id}/index` 对非 CONVERTED 文档返回 422
- [ ] `POST /admin/convert-pending` 的 dry_run 模式返回正确的待转换列表
- [ ] `POST /admin/convert-pending` 的 document_ids 过滤正确
- [ ] force=true 可强制重新转换已完成文档
- [ ] 所有端点错误响应符合规范

### Phase 4: 集成层 — 智能关联与测试

| # | 任务 | 文件 | 依赖 |
|---|------|------|------|
| 4.1 | 实现 `_determine_processing_action()` | `application/services/notebook_document_service.py` | 1.2 |
| 4.2 | 重构 `add_documents()` 使用智能补齐逻辑 | `application/services/notebook_document_service.py` | 4.1, 2.3, 2.5 |
| 4.3 | 新增 `_enqueue_indexing()` 方法 | `application/services/notebook_document_service.py` | 2.5 |
| 4.4 | AddDocumentsResult 响应新增 `action` 字段 | `api/models.py` + `api/routers/notebook_documents.py` | 4.2 |
| 4.5 | 编写单元测试 | `tests/` | 全部 |
| 4.6 | 编写集成测试 | `tests/` | 全部 |
| 4.7 | 端到端测试：先转换后关联流程 | — | 全部 |

**验收标准**：
- [ ] UPLOADED 文档加入 Notebook → action=full_pipeline（向后兼容）
- [ ] CONVERTED 文档加入 Notebook → action=index_only（跳过转换）
- [ ] COMPLETED 文档加入 Notebook → action=none（直接关联）
- [ ] FAILED(有 content_path) 文档加入 Notebook → action=index_only
- [ ] FAILED(无 content_path) 文档加入 Notebook → action=full_pipeline
- [ ] 响应中 action 字段正确
- [ ] 并发关联不产生重复处理

## 3. 依赖关系图

```
Phase 1                    Phase 2                   Phase 3         Phase 4
┌─────────┐               ┌──────────┐              ┌──────────┐    ┌──────────┐
│ 1.1     │──────────────▶│ 2.9      │              │          │    │          │
│ Stage   │               │ 替换硬编码 │              │          │    │          │
│ Enum    │──┐            └──────────┘              │          │    │          │
└─────────┘  │                                      │          │    │          │
             │            ┌──────────┐              │          │    │          │
┌─────────┐  ├───────────▶│ 2.2-2.3  │─────────────▶│ 3.2      │    │          │
│ 1.2     │──┤            │ convert  │              │ convert  │    │          │
│ CONVERTED│  │            │ task     │              │ endpoint │    │          │
└────┬────┘  │            └──────────┘              └──────────┘    │          │
     │       │            ┌──────────┐              ┌──────────┐    │          │
┌────▼────┐  ├───────────▶│ 2.4-2.5  │─────────────▶│ 3.3      │───▶│ 4.1-4.4 │
│ 1.3     │──┤            │ index    │              │ index    │    │ 智能关联  │
│ Entity  │  │            │ task     │              │ endpoint │    │          │
└─────────┘  │            └──────────┘              └──────────┘    │          │
             │            ┌──────────┐              ┌──────────┐    │          │
┌─────────┐  └───────────▶│ 2.6      │              │ 3.4      │    │          │
│ 1.4     │──────────────▶│ refactor │              │ batch    │───▶│ 4.5-4.7 │
│ claim   │               │ pipeline │              │ convert  │    │ 测试     │
└─────────┘               └──────────┘              └──────────┘    └──────────┘
```

## 4. 风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| State Machine 变更影响已有文档 | 低 | 中 | CONVERTED 是新增值，不影响现有 5 个状态 |
| claim_processing 参数化破坏并发安全 | 低 | 高 | 保持 SQL WHERE + CAS 原子操作 |
| 前端未适配 CONVERTED 状态 | 中 | 低 | 前端 switch/case 加 default 分支即可 |
| 重构 _process_document_async 引入 regression | 中 | 高 | 完整回归测试 + 保持函数签名不变 |
| Celery Task 注册名冲突 | 低 | 中 | 使用完整模块路径作为 task name |

## 5. 测试策略

### 5.1 单元测试

```python
# test_document_status.py
def test_converted_status_properties():
    assert DocumentStatus.CONVERTED.is_stable == True
    assert DocumentStatus.CONVERTED.is_terminal == False
    assert DocumentStatus.CONVERTED.can_start_indexing == True

# test_processing_stage.py
def test_stage_serialization():
    assert ProcessingStage.CONVERTING.value == "converting"
    assert ProcessingStage.CONVERTING.is_conversion_phase == True

# test_determine_action.py
def test_uploaded_needs_full_pipeline():
    doc = Document(status=UPLOADED)
    assert _determine_processing_action(doc) == "full_pipeline"

def test_converted_needs_index_only():
    doc = Document(status=CONVERTED, content_path="xxx/content.md")
    assert _determine_processing_action(doc) == "index_only"

def test_completed_needs_nothing():
    doc = Document(status=COMPLETED)
    assert _determine_processing_action(doc) == "none"
```

### 5.2 集成测试

```python
# test_convert_endpoint.py
async def test_convert_document_uploaded():
    """测试: UPLOADED → convert → CONVERTED"""
    doc = await upload_test_pdf()
    resp = await client.post(f"/admin/documents/{doc.id}/convert")
    assert resp.status_code == 202
    # 等待转换完成
    doc = await poll_status(doc.id, target="converted")
    assert doc.content_path is not None

async def test_index_document_converted():
    """测试: CONVERTED → index → COMPLETED"""
    doc = await create_converted_document()
    resp = await client.post(f"/admin/documents/{doc.id}/index")
    assert resp.status_code == 202
    doc = await poll_status(doc.id, target="completed")
    assert doc.chunk_count > 0

async def test_add_converted_to_notebook():
    """测试: 已转换文档加入 Notebook → index_only"""
    doc = await create_converted_document()
    notebook = await create_notebook()
    resp = await client.post(
        f"/notebooks/{notebook.id}/documents",
        json={"document_ids": [doc.id]},
    )
    data = resp.json()
    assert data["added"][0]["action"] == "index_only"
```

### 5.3 端到端测试场景

| 场景 | 步骤 | 预期 |
|------|------|------|
| 仅转换 | upload → convert → check status | CONVERTED, content.md 存在 |
| 转换后索引 | upload → convert → index → check | COMPLETED, chunk_count > 0 |
| 先转换后关联 | upload → convert → add to notebook | action=index_only |
| 传统流程 | upload → add to notebook | action=full_pipeline |
| 批量转换 | upload 3 docs → convert-pending | 3 个文档均 CONVERTED |
| 失败重试 | upload → convert → fail indexing → index | 从索引重试成功 |

## 6. 里程碑

| 里程碑 | 包含 Phase | 预计工时 | 说明 |
|--------|-----------|---------|------|
| M1: 基础就绪 | Phase 1 | 2h | 状态机扩展，无功能变更 |
| M2: Task 拆分 | Phase 2 | 4h | 核心拆分，可通过 Celery 直接调用验证 |
| M3: API 可用 | Phase 3 | 2h | 新端点上线，可通过 Postman 测试 |
| M4: 全面集成 | Phase 4 | 3h | 智能关联 + 完整测试 |

**总预计工时**：约 11h

## 7. 回滚方案

如果改进引入严重问题：

1. **Phase 1 回滚**：删除 `CONVERTED` 枚举值和 `ProcessingStage` 文件。数据库中不会有 CONVERTED 状态的记录（需要人工确认）
2. **Phase 2 回滚**：恢复 `_process_document_async()` 原始实现，删除新增 Task
3. **Phase 3 回滚**：删除新增路由，恢复 admin.py
4. **Phase 4 回滚**：恢复 `add_documents()` 原始逻辑

每个 Phase 可以独立回滚，不影响前序 Phase。
