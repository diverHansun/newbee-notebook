# Improve-6 删除端点语义修正

本文档修正三个删除相关端点的语义边界，明确软删除(清索引)和硬删除(含文件系统)的区分。

---

## 1. 三端点职责定义

### 1.1 端点总览

| 端点 | 语义 | 操作范围 | 是否删除文件系统 |
|------|------|---------|----------------|
| `DELETE /notebooks/{notebook_id}/documents/{document_id}` | 取消关联 | 仅删除 notebook-document 关联关系 | 否 |
| `DELETE /documents/{document_id}` | 软删除 | 清除索引数据 + 删除 DB 记录，保留文件 | 否 |
| `DELETE /library/documents/{document_id}?force=true` | 硬删除(Force) | 清除索引 + 删除 DB 记录 + 删除文件系统 | 是 |

### 1.2 语义层次图

```
操作层次 (从轻到重):

Level 1 -- 取消关联 (Remove from Notebook)
  DELETE /notebooks/{nid}/documents/{did}
  |
  | 只删除 notebook_document_ref 关联记录
  | 递减 notebook.document_count
  | 文档本身不受影响，仍可从其他 notebook 或 library 访问
  |
  v

Level 2 -- 软删除 (Delete Document)
  DELETE /documents/{did}
  |
  | 包含 Level 1 的全部操作 (清除所有 notebook 关联)
  | 异步删除 pgvector 向量节点
  | 异步删除 Elasticsearch 索引节点
  | 删除 messages 表中的 source 引用标记 (mark_source_deleted)
  | 删除 documents 表中的数据库记录
  | ** 不删除 ** data/documents/{did}/ 目录
  |
  v

Level 3 -- 硬删除 (Force Delete Library Document)
  DELETE /library/documents/{did}?force=true
  |
  | 包含 Level 2 的全部操作
  | ** 额外 ** 删除文件系统: data/documents/{did}/
  |   - original/ (原始 PDF 等)
  |   - markdown/ (MinerU 转换后的 Markdown)
  |   - assets/ (提取的图片等)
  |
  v

[清理完毕]
```

---

## 2. 当前实现问题

### 2.1 问题描述

当前 `DELETE /documents/{did}` 和 `DELETE /library/documents/{did}` 调用同一个 `DocumentService.delete_document()` 方法，该方法执行了 Level 3 的完整硬删除操作:

```python
# 当前 document_service.py
async def delete_document(self, document_id, force=False):
    ...
    delete_document_nodes_task.delay(document_id)   # 清索引
    self._delete_document_files(document_id)         # 删文件系统
    await self._document_repo.delete(document_id)    # 删 DB 记录
```

无论是否传入 `force=True`，都会执行文件系统删除，这与期望的语义不符。

### 2.2 impact

- `DELETE /documents/{did}` 破坏力过大，用户无法"只清索引保留源文件"
- 无法实现"重新处理文档"的工作流(清除旧索引 -> 重新触发转换 -> 重建索引)

---

## 3. 改造方案

### 3.1 DocumentService 方法拆分

将当前的 `delete_document()` 拆分为两个方法:

```python
class DocumentService:

    async def delete_document(self, document_id: str) -> None:
        """软删除: 清除索引数据和 DB 记录，保留文件系统。

        操作步骤:
        1. 查找文档，不存在则抛出 ValueError
        2. mark_source_deleted() -- 保留聊天引用中的文档标题
        3. 删除所有 notebook_document_ref 关联 + 递减 notebook.document_count
        4. 异步删除 pgvector 向量节点 (Celery task)
        5. 异步删除 Elasticsearch 索引节点 (Celery task)
        6. 删除 documents 表中的数据库记录
        ** 不执行文件系统删除 **
        """
        doc = await self._document_repo.get(document_id)
        if not doc:
            raise ValueError(f"Document not found: {document_id}")

        await self._mark_source_deleted(document_id, doc.title)
        await self._delete_notebook_refs(document_id)
        delete_document_nodes_task.delay(document_id)
        await self._document_repo.delete(document_id)

    async def force_delete_document(self, document_id: str) -> None:
        """硬删除: 软删除 + 文件系统清除。

        执行 delete_document() 的全部操作，额外删除:
        - data/documents/{document_id}/original/ (原始文件)
        - data/documents/{document_id}/markdown/ (转换后内容)
        - data/documents/{document_id}/assets/ (图片等资产)
        - data/documents/{document_id}/ (整个目录)
        """
        await self.delete_document(document_id)
        self._delete_document_files(document_id)
```

### 3.2 路由层改造

**`DELETE /documents/{document_id}` -- 软删除**:

```python
# api/routers/documents.py
@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: str = Path(...),
    service: DocumentService = Depends(get_document_service),
):
    """软删除文档: 清除索引数据和 DB 记录，保留文件系统中的原文件和 Markdown。"""
    try:
        await service.delete_document(document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")
```

**`DELETE /library/documents/{document_id}` -- 硬删除(需 force=true)**:

```python
# api/routers/library.py
@router.delete("/library/documents/{document_id}", status_code=204)
async def delete_library_document(
    document_id: str = Path(...),
    force: bool = Query(False),
    service: DocumentService = Depends(get_document_service),
):
    """从 Library 删除文档。

    force=false: 执行软删除(清索引 + 删 DB 记录，保留文件)
    force=true:  执行硬删除(含文件系统清除)
    """
    try:
        if force:
            await service.force_delete_document(document_id)
        else:
            await service.delete_document(document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")
```

**`DELETE /notebooks/{notebook_id}/documents/{document_id}` -- 取消关联(不变)**:

```python
# api/routers/notebook_documents.py -- 保持不变
@router.delete("/notebooks/{notebook_id}/documents/{document_id}", status_code=204)
async def remove_document_from_notebook(
    notebook_id: str,
    document_id: str,
    service: NotebookDocumentService = Depends(get_notebook_document_service),
):
    """取消 notebook 和 document 的关联关系。不影响文档本身。"""
    await service.remove_document(notebook_id, document_id)
```

---

## 4. 删除操作对比矩阵

| 操作 | 取消关联 | 软删除 | 硬删除 |
|------|---------|--------|--------|
| 删除 notebook_document_ref | 仅当前 notebook | 所有 notebook | 所有 notebook |
| 递减 notebook.document_count | 当前 notebook | 所有关联 notebook | 所有关联 notebook |
| mark_source_deleted | 否 | 是 | 是 |
| 删除 pgvector nodes | 否 | 是 (异步) | 是 (异步) |
| 删除 ES nodes | 否 | 是 (异步) | 是 (异步) |
| 删除 documents 表记录 | 否 | 是 | 是 |
| 删除 data/documents/{id}/ | 否 | 否 | 是 |

---

## 5. 数据流图

### 5.1 软删除流程

```
客户端 DELETE /documents/{did}
    |
    v
DocumentService.delete_document(did)
    |
    +-- [1] mark_source_deleted(did, title)
    |       将 references 表中该 document 的引用标记为已删除
    |       保留 title 便于前端显示"[已删除] xxx"
    |
    +-- [2] delete_notebook_refs(did)
    |       删除 notebook_document_ref 表中所有 document_id=did 的记录
    |       遍历关联的 notebook，递减 document_count
    |
    +-- [3] delete_document_nodes_task.delay(did)  [异步 Celery]
    |       删除 pgvector 中 ref_doc_id=did 的所有向量节点
    |       删除 Elasticsearch 中 document_id=did 的所有索引文档
    |
    +-- [4] document_repo.delete(did)
    |       删除 documents 表中的记录
    |
    v
  完成 (文件系统中 data/documents/{did}/ 保留)
```

### 5.2 硬删除流程

```
客户端 DELETE /library/documents/{did}?force=true
    |
    v
DocumentService.force_delete_document(did)
    |
    +-- [1-4] delete_document(did)     # 执行全部软删除步骤
    |
    +-- [5] _delete_document_files(did)
    |       path = DOCUMENTS_DIR / did
    |       if path.exists():
    |           shutil.rmtree(path)    # 递归删除整个目录
    |       删除内容:
    |         data/documents/{did}/original/    (原始文件)
    |         data/documents/{did}/markdown/    (Markdown 内容)
    |         data/documents/{did}/assets/      (图片等)
    |
    v
  完成 (文件系统已清理)
```

---

## 6. Postman Collection 更新

需要更新 Postman Collection 中对应的测试用例描述:

| 用例 | 更新内容 |
|------|---------|
| Delete Document | 明确标注为"软删除"，说明文件系统保留 |
| Delete Library Document | 增加 `force=true` 参数说明，区分软删除和硬删除 |
| Remove Document from Notebook | 明确标注为"仅取消关联"，不影响文档数据 |

---

## 7. 需要修改的文件

| 文件 | 改动类型 | 改动内容 |
|------|---------|---------|
| `application/services/document_service.py` | 重构 | `delete_document()` 拆分为软删除; 新增 `force_delete_document()` 硬删除 |
| `api/routers/documents.py` | 调整 | `delete_document` 端点移除文件系统删除逻辑 |
| `api/routers/library.py` | 调整 | `delete_library_document` 端点根据 `force` 参数调用不同方法 |
| `postman_collection.json` | 更新 | 更新三个删除端点的描述和示例 |
