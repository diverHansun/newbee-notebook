# 05 - 智能 Notebook 关联逻辑

## 1. 概述

当用户将 Library 中的文档添加到 Notebook 时，系统需要自动检测文档的处理状态，仅执行缺失的阶段，避免重复劳动。

核心原则：用户端只看到完整流水线行为（"添加文档后可以对话"），底层自动优化执行路径。

## 2. 决策矩阵

### 2.1 文档状态与处理动作

当文档被关联到 Notebook 时，系统根据文档当前状态决定处理动作：

| 文档状态 | content_path | 处理动作 | 触发的 Task | force | 说明 |
|----------|-------------|---------|------------|-------|------|
| UPLOADED | 无 | 完整流水线 | `process_document_task` | False | 需要转换+索引 |
| PENDING | 无 | 无操作 | -- | -- | 已在队列中，等待执行 |
| PROCESSING | -- | 无操作 | -- | -- | 正在处理中 |
| CONVERTED | 有 | 仅索引 | `index_document_task` | False | 已转换，补齐索引 |
| COMPLETED | 有 | 无操作 | -- | -- | 已完成，直接关联 |
| FAILED (有 content_path) | 有 | 仅索引 | `index_document_task` | **True** | 需要 force 才能 claim FAILED 状态 |
| FAILED (无 content_path) | 无 | 完整流水线 | `process_document_task` | False | 转换也失败了，重头来 |

### 2.2 决策逻辑

```python
def _determine_processing_action(
    document: Document,
) -> tuple[str, str | None, bool]:
    """
    确定文档加入 Notebook 时需要的处理动作。

    Returns:
        (action, task_name, force)
        action: "full_pipeline" | "index_only" | "none"
        task_name: 要触发的 Celery task 名称，"none" 时为 None
        force: 是否需要 force=True（当文档状态不在 task 默认 from_statuses 中时）
    """
    if document.status == DocumentStatus.COMPLETED:
        return "none", None, False

    if document.status in (DocumentStatus.PENDING, DocumentStatus.PROCESSING):
        return "none", None, False

    if document.status == DocumentStatus.CONVERTED:
        return "index_only", "index_document", False

    if document.status == DocumentStatus.FAILED and document.content_path:
        # FAILED 不在 index_document_task 的默认 from_statuses=[CONVERTED] 中，
        # 必须传 force=True 以将 FAILED 加入 from_statuses，
        # 否则 claim_processing 会因状态不匹配而静默跳过。
        return "index_only", "index_document", True

    # UPLOADED 或 FAILED(无 content_path)
    return "full_pipeline", "process_document", False
```

## 3. NotebookDocumentService 变更

### 3.1 add_documents 方法

```python
async def add_documents(
    self, notebook_id: str, document_ids: list[str]
) -> list[AddDocumentResult]:
    results = []
    for doc_id in document_ids:
        document = await self._document_repo.get(doc_id)
        if not document:
            results.append(AddDocumentResult(
                document_id=doc_id, success=False,
                error="Document not found", action="none",
            ))
            continue

        # 关联（创建 notebook_document 记录）
        await self._notebook_doc_repo.add(notebook_id, doc_id)

        # 决定处理动作
        action, task_name, force = self._determine_processing_action(document)

        if task_name == "process_document":
            process_document_task.delay(doc_id)
        elif task_name == "index_document":
            index_document_task.delay(doc_id, force=force)

        results.append(AddDocumentResult(
            document_id=doc_id, success=True,
            action=action,
        ))

    await self._session.commit()
    return results
```

### 3.2 AddDocumentResult 扩展

```python
class AddDocumentResult(BaseModel):
    document_id: str
    success: bool
    error: str | None = None
    action: str  # "full_pipeline" | "index_only" | "none"
```

`action` 字段告知前端为该文档触发了什么操作，前端可据此显示不同的处理状态提示。

## 4. 对话 blocking 行为

### 4.1 blocking_statuses 更新

```python
# chat_service.py -> _get_notebook_scope()
blocking_statuses = {
    DocumentStatus.UPLOADED,
    DocumentStatus.PENDING,
    DocumentStatus.PROCESSING,
    DocumentStatus.CONVERTED,   # 新增：有转换产物但未索引，不参与 RAG
}
```

### 4.2 行为说明

- CONVERTED 文档不参与 RAG 检索（没有向量索引）
- CONVERTED 文档算作"未就绪"文档，计入 `processing_count`
- 当 Notebook 中所有文档要么 COMPLETED 要么不在关联列表中时，对话正常进行
- 前端可以通过 `processing_count > 0` 提示"部分文档正在处理中"

### 4.3 时间窗口分析

在正常用户流程（关联文档到 Notebook）中，CONVERTED 文档关联后会立即触发 `index_document_task`，文档迅速进入 `PROCESSING` 状态。CONVERTED 在对话中出现的窗口期极短（秒级），不影响用户体验。

## 5. 边界情况处理

### 5.1 批量添加（混合状态）

一次添加 5 个文档，状态各异：

| 文档 | 状态 | 动作 |
|------|------|------|
| doc-1 | UPLOADED | full_pipeline |
| doc-2 | COMPLETED | none |
| doc-3 | CONVERTED | index_only |
| doc-4 | FAILED (有 content_path) | index_only |
| doc-5 | PROCESSING | none |

每个文档独立决策，互不影响。

### 5.2 重复添加

文档已在 Notebook 中，再次添加：
- 关联层面：幂等，不创建重复记录
- 处理层面：COMPLETED 文档不触发新 task
- PROCESSING 文档不触发新 task（避免重复）

### 5.3 文档被多个 Notebook 关联

文档的索引是全局的（library 级别），Notebook 只记录关联关系。同一文档被多个 Notebook 关联时，索引只执行一次，后续关联直接生效。
