# 05 - 智能 Notebook 关联逻辑：阶段验证与缺失补齐

## 1. 概述

当文档加入 Notebook 时，系统应**智能检测**文档已完成的处理阶段，只补齐缺失部分而非完整重跑。这是 improve-8 的核心产品价值——支持"先转换、后关联"的灵活工作流。

## 2. 当前行为

```python
# notebook_document_service.py — 当前逻辑
async def add_documents(self, notebook_id, document_ids):
    for document_id in document_ids:
        # 1. 建立关联
        create NotebookDocumentRef
        
        # 2. 如果未处理，触发完整流水线
        if document.status in (UPLOADED, FAILED):
            update_status(PENDING)
            process_document_task.delay(document_id)  # 完整流水线
```

**问题**：没有考虑 `CONVERTED` 状态——已转换的文档加入 Notebook 时不应该重新转换。

## 3. 改进后行为

### 3.1 决策矩阵

当文档加入 Notebook 时，根据文档状态决定处理动作：

| 文档状态 | 动作 | 触发的 Task | 说明 |
|----------|------|------------|------|
| **UPLOADED** | 完整流水线 | `process_document_task` | 需要转换 + 索引 |
| **FAILED** (无 content_path) | 完整流水线 | `process_document_task` | 转换也失败了，需要全部重来 |
| **FAILED** (有 content_path) | 仅索引 | `index_document_task` | 转换成功但索引失败，只需重做索引 |
| **CONVERTED** | 仅索引 | `index_document_task` | 已转换，只需索引 |
| **PENDING** | 不触发 | — | 已在队列中等待 |
| **PROCESSING** | 不触发 | — | 正在处理中 |
| **COMPLETED** | 不触发 | — | 已就绪，直接关联 |

### 3.2 核心判断逻辑

```python
def _determine_processing_action(document: Document) -> str:
    """
    根据文档状态确定关联到 Notebook 时需要的处理动作。
    
    Returns:
        "full_pipeline" — 需要完整流水线（转换 + 索引）
        "index_only"    — 只需要索引
        "none"          — 不需要任何处理
    """
    if document.status == DocumentStatus.COMPLETED:
        return "none"
    
    if document.status in (DocumentStatus.PENDING, DocumentStatus.PROCESSING):
        return "none"
    
    if document.status == DocumentStatus.CONVERTED:
        return "index_only"
    
    if document.status == DocumentStatus.FAILED:
        # 判断转换是否成功过（content_path 存在 = 转换完成过）
        if document.content_path:
            content_abs_path = Path(get_documents_directory()) / document.content_path
            if content_abs_path.exists():
                return "index_only"
        return "full_pipeline"
    
    if document.status == DocumentStatus.UPLOADED:
        return "full_pipeline"
    
    return "full_pipeline"  # 安全默认
```

### 3.3 改进后的 add_documents 实现

```python
async def add_documents(
    self,
    notebook_id: str,
    document_ids: list[str],
) -> AddDocumentsResult:
    notebook = await self._notebook_repo.get(notebook_id)
    if not notebook:
        raise NotebookNotFoundError(notebook_id)
    
    added = []
    skipped = []
    failed = []
    
    for document_id in document_ids:
        document = await self._document_repo.get(document_id)
        if not document:
            failed.append({"document_id": document_id, "reason": "Document not found"})
            continue
        
        if not document.is_library_document:
            failed.append({"document_id": document_id, "reason": "Not a library document"})
            continue
        
        # 检查是否已关联
        existing_ref = await self._ref_repo.get_by_notebook_and_document(
            notebook_id, document_id
        )
        if existing_ref:
            skipped.append({"document_id": document_id, "reason": "Already associated"})
            continue
        
        # 建立关联
        ref = NotebookDocumentRef(
            notebook_id=notebook_id,
            document_id=document_id,
        )
        await self._ref_repo.create(ref)
        notebook.document_count += 1
        
        # ── 智能处理决策 ──
        action = _determine_processing_action(document)
        
        if action == "full_pipeline":
            await self._document_repo.update_status(
                document_id,
                status=DocumentStatus.PENDING,
                processing_stage=ProcessingStage.QUEUED.value,
            )
            await self._session.commit()
            await self._enqueue_processing(document_id, mode="full")
            added.append({
                "document_id": document_id,
                "status": "queued",
                "action": "full_pipeline",
            })
            
        elif action == "index_only":
            # CONVERTED 或 FAILED(有content_path) → 仅索引
            await self._document_repo.update_status(
                document_id,
                status=DocumentStatus.CONVERTED if document.status == DocumentStatus.FAILED else document.status,
                processing_stage=ProcessingStage.QUEUED.value,
            )
            await self._session.commit()
            await self._enqueue_indexing(document_id)
            added.append({
                "document_id": document_id,
                "status": "queued",
                "action": "index_only",
            })
            
        else:  # "none"
            await self._session.commit()
            added.append({
                "document_id": document_id,
                "status": document.status.value,
                "action": "none",
            })
    
    await self._session.commit()
    
    return AddDocumentsResult(
        notebook_id=notebook_id,
        added=added,
        skipped=skipped,
        failed=failed,
    )


async def _enqueue_processing(self, document_id: str, mode: str = "full"):
    """触发完整流水线处理。"""
    from newbee_notebook.infrastructure.tasks.document_tasks import process_document_task
    process_document_task.delay(document_id)


async def _enqueue_indexing(self, document_id: str):
    """触发仅索引处理。"""
    from newbee_notebook.infrastructure.tasks.document_tasks import index_document_task
    index_document_task.delay(document_id)
```

## 4. 响应格式增强

### 4.1 AddDocumentsResult 新增 action 字段

```json
{
  "notebook_id": "uuid-notebook",
  "added": [
    {
      "document_id": "uuid-1",
      "status": "queued",
      "action": "full_pipeline"
    },
    {
      "document_id": "uuid-2",
      "status": "queued",
      "action": "index_only"
    },
    {
      "document_id": "uuid-3",
      "status": "completed",
      "action": "none"
    }
  ],
  "skipped": [],
  "failed": []
}
```

`action` 字段让前端/调用方明确知道每个文档触发了什么操作：

| action 值 | 含义 |
|-----------|------|
| `full_pipeline` | 触发完整流水线（转换 + 索引）|
| `index_only` | 仅触发索引（已有转换结果）|
| `none` | 无需任何处理（已完成或正在处理）|

## 5. 工作流场景

### 5.1 场景 A：传统流程（向后兼容）

```
1. Upload PDF → status=UPLOADED
2. Add to Notebook → action=full_pipeline → process_document_task
3. Wait for COMPLETED
4. Chat
```

与当前行为完全一致。

### 5.2 场景 B：先转换后关联

```
1. Upload PDF → status=UPLOADED
2. POST /admin/documents/{id}/convert → status=CONVERTED
   (用户可以在此时查看转换质量，确认 Markdown 正确)
3. Add to Notebook → action=index_only → index_document_task
   (跳过 MinerU 转换，直接索引)
4. Wait for COMPLETED
5. Chat
```

MinerU 转换和 Notebook 关联**解耦**，转换可以提前完成。

### 5.3 场景 C：批量预转换

```
1. Upload 10 PDFs → all status=UPLOADED
2. POST /admin/convert-pending → all status=CONVERTED
   (10个文档并行/顺序转换，不需要任何 Notebook)
3. 创建 Notebook
4. Add 5 documents to Notebook → all action=index_only
   (只索引，不再转换)
5. Chat on Notebook
```

### 5.4 场景 D：索引失败重试

```
1. PDF uploaded + converted → CONVERTED
2. Add to Notebook → index_only → pgvector 连接失败 → FAILED (content_path 保留)
3. 修复 pgvector
4. POST /admin/documents/{id}/index → 重试索引 → COMPLETED
   (无需重新转换)
```

### 5.5 场景 E：已完成文档关联到新 Notebook

```
1. Document COMPLETED (在 Notebook A 中已完成)
2. Add to Notebook B → action=none
   (已有索引，直接关联，无需任何处理)
```

## 6. 对话就绪条件

文档能否参与对话的判断逻辑需要更新：

```python
def can_chat_with_document(document: Document) -> bool:
    """判断文档是否可以参与对话。"""
    return document.status == DocumentStatus.COMPLETED
```

> `CONVERTED` 状态的文档**不能参与对话**（没有向量索引），必须先完成索引。

Notebook 的对话端点应在查询关联文档时过滤出 `COMPLETED` 状态的文档作为 RAG 知识源。

## 7. 边界情况处理

### 7.1 FAILED 文档的 content_path 可靠性

当 FAILED 文档有 `content_path` 时，需要验证磁盘文件是否真的存在：

```python
if document.content_path:
    content_abs = Path(get_documents_directory()) / document.content_path
    if content_abs.exists():
        return "index_only"    # 转换产物存在，可以直接索引
    else:
        return "full_pipeline" # 转换产物丢失，需要重新转换
```

### 7.2 并发关联

如果同一文档被同时加入两个 Notebook：

- `NotebookDocumentRef` 的唯一约束防止重复关联
- `claim_processing()` 原子 CAS 防止重复处理
- 第一个到达的触发处理，后续的 `action=none`

### 7.3 processing_meta 记录触发来源

为方便排查，在 `processing_meta` 中记录触发来源：

```python
processing_meta = {
    "trigger": "notebook_association",
    "notebook_id": notebook_id,
    "action": "index_only",
}
```

## 8. 向后兼容性

| 方面 | 兼容性 |
|------|--------|
| API 响应格式 | added 列表中新增 `action` 字段（新增字段，不破坏现有结构）|
| UPLOADED 文档 | 行为与现有完全一致 |
| COMPLETED 文档 | 行为与现有完全一致 |
| FAILED 文档 | 增强：有 content_path 时智能跳过转换 |
| 前端 | 需要适配 `action` 字段和 `converted` 状态显示 |
