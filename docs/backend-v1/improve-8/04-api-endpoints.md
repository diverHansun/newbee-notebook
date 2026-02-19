# 04 - API 端点设计

## 1. 概述

本文档定义 Improve-8 引入的 Admin API 端点。这些端点用于开发调试和运维排查，不是用户态功能。

新增端点总览：

| 端点 | 方法 | 用途 |
|------|------|------|
| `/admin/documents/{id}/convert` | POST | 仅转换单个文档 |
| `/admin/documents/{id}/index` | POST | 仅索引单个文档 |
| `/admin/convert-pending` | POST | 批量转换待处理文档 |
| `/admin/index-pending` | POST | 批量索引已转换文档 |

现有端点变更：

| 端点 | 变更说明 |
|------|---------|
| `POST /admin/documents/{id}/reindex` | 支持智能跳过转换阶段 |
| `GET /library/documents` | 支持 `status=converted` 过滤 |
| `GET /admin/index-stats` | 统计包含 `converted` 状态计数 |

## 2. 新增端点：单文档转换

```
POST /api/v1/admin/documents/{document_id}/convert
```

### 请求参数

| 参数 | 类型 | 位置 | 说明 |
|------|------|------|------|
| document_id | string (UUID) | path | 文档 ID |
| force | bool | query, 默认 false | 是否强制重转换 |

### 前置条件检查

| 当前状态 | force=false 行为 | force=true 行为 |
|----------|----------------|----------------|
| UPLOADED / FAILED | 正常触发 | 正常触发 |
| PENDING / PROCESSING | 拒绝 (409) | 拒绝 (409) |
| CONVERTED | 跳过 (200, 已转换) | 重置为 UPLOADED，清理旧索引，重新转换 |
| COMPLETED | 跳过 (200, 已完成) | 重置为 UPLOADED，清理旧索引，重新转换 |

### 响应

```json
{
  "document_id": "uuid",
  "status": "queued",
  "message": "Convert task queued",
  "action": "convert_only"
}
```

### 实现要点

force=true 时的清理逻辑内联到 `convert_document_task` 中执行（非异步分发），避免竟态条件：

```python
@router.post("/documents/{document_id}/convert")
async def convert_document(document_id: str, force: bool = False, ...):
    doc = await document_repo.get(document_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    if doc.status in {DocumentStatus.PENDING, DocumentStatus.PROCESSING}:
        raise HTTPException(409, f"Document is {doc.status.value}")

    if not force and doc.status in {DocumentStatus.CONVERTED, DocumentStatus.COMPLETED}:
        return {"document_id": document_id, "status": doc.status.value,
                "message": "Already converted/completed", "action": "none"}

    convert_document_task.delay(document_id, force=force)
    return {"document_id": document_id, "status": "queued",
            "message": "Convert task queued", "action": "convert_only"}
```

## 3. 新增端点：单文档索引

```
POST /api/v1/admin/documents/{document_id}/index
```

### 请求参数

| 参数 | 类型 | 位置 | 说明 |
|------|------|------|------|
| document_id | string (UUID) | path | 文档 ID |
| force | bool | query, 默认 false | 是否强制重索引 |

### 前置条件检查

| 当前状态 | force=false 行为 | force=true 行为 |
|----------|----------------|----------------|
| CONVERTED | 正常触发 | 正常触发 |
| UPLOADED / PENDING | 拒绝 (400, 需要先转换) | 拒绝 (400, 需要先转换) |
| PROCESSING | 拒绝 (409) | 拒绝 (409) |
| COMPLETED | 跳过 (200, 已完成) | 清理旧索引，重新索引 |
| FAILED (有 content_path) | 正常触发 | 正常触发 |
| FAILED (无 content_path) | 拒绝 (400, 需要先转换) | 拒绝 (400, 需要先转换) |

### 响应

```json
{
  "document_id": "uuid",
  "status": "queued",
  "message": "Index task queued",
  "action": "index_only"
}
```

## 4. 新增端点：批量转换

```
POST /api/v1/admin/convert-pending
```

### 请求体

```json
{
  "document_ids": ["uuid1", "uuid2"],
  "dry_run": false
}
```

- `document_ids` 可选。为空时转换所有 UPLOADED / FAILED 文档。
- `dry_run` 可选。为 true 时仅返回待转换列表，不实际触发。

### 响应

```json
{
  "queued_count": 5,
  "document_ids": ["uuid1", "uuid2", "uuid3", "uuid4", "uuid5"]
}
```

### 实现要点

批量操作为每个文档分派独立的 `convert_document_task`，不在单个函数中循环 await。

## 5. 新增端点：批量索引

```
POST /api/v1/admin/index-pending
```

### 请求体

```json
{
  "document_ids": ["uuid1", "uuid2"],
  "dry_run": false
}
```

- `document_ids` 可选。为空时索引所有 CONVERTED 文档。
- `dry_run` 可选。

### 响应

```json
{
  "queued_count": 3,
  "document_ids": ["uuid1", "uuid2", "uuid3"]
}
```

### 实现要点

查找 `CONVERTED` 状态文档，为每个分派 `index_document_task`。与批量转换结构对称。

## 6. 现有端点变更

### 6.1 POST /admin/documents/{id}/reindex

变更要点：支持智能跳过。

- 如果文档 `content_path` 存在（说明转换产物完整），不再重置为 PENDING 后跑完整流水线，而是直接分派 `index_document_task`
- 如果文档 `content_path` 不存在，行为不变，分派 `process_document_task`
- force=true 时始终执行完整流水线

```python
@router.post("/documents/{document_id}/reindex")
async def reindex_document(document_id: str, force: bool = False, ...):
    doc = await document_repo.get(document_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    if not force and doc.status in {DocumentStatus.PENDING, DocumentStatus.PROCESSING}:
        raise HTTPException(400, f"Document status={doc.status.value}")

    # 智能判断：有转换产物则仅重索引
    if not force and doc.content_path:
        # 注意：不单独分派 delete_document_nodes_task。
        # force=True 时 _do_index 内部会同步执行旧索引清理，
        # 避免"清理未完成就开始索引"的竟态条件（见决策 #11）。
        index_document_task.delay(document_id, force=True)
        return ReindexResponse(
            document_id=document_id, status="queued",
            message="Index-only task queued (conversion preserved)",
        )

    # 完整重处理：force=True 时 _do_full_pipeline 内部处理清理
    await document_repo.update_status(document_id, DocumentStatus.PENDING, ...)
    await document_repo.commit()
    process_document_task.delay(document_id)
    return ReindexResponse(
        document_id=document_id, status="queued",
        message="Full reindex task queued",
    )
```

### 6.2 GET /library/documents

`status` 查询参数新增 `converted` 合法值，用于筛选已转换但未索引的文档。

### 6.3 GET /admin/index-stats

`documents_by_status` 响应中自动包含 `"converted"` 的计数（因为 DocumentStatus 枚举已扩展）。

## 7. 端点汇总与 HTTP 状态码

| 端点 | 成功 | 文档不存在 | 状态冲突 | 前置条件不满足 |
|------|------|-----------|---------|--------------|
| POST .../convert | 200 | 404 | 409 | -- |
| POST .../index | 200 | 404 | 409 | 400 |
| POST convert-pending | 200 | -- | -- | -- |
| POST index-pending | 200 | -- | -- | -- |
| POST .../reindex | 200 | 404 | 400 | -- |
