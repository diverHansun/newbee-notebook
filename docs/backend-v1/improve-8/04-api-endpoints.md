# 04 - API 端点设计：Admin 独立操作端点

## 1. 概述

新增 3 个 Admin 端点，提供文档转换和索引的独立触发能力。所有新端点在 `/admin/` 路径下，与现有 admin 端点（`reprocess-pending`, `reindex`, `index-stats`）风格一致。

## 2. 新增端点一览

| 方法 | 路径 | 说明 | 对应 Celery Task |
|------|------|------|-----------------|
| `POST` | `/admin/documents/{id}/convert` | 单文档仅转换 | `convert_document_task` |
| `POST` | `/admin/documents/{id}/index` | 单文档仅索引 | `index_document_task` |
| `POST` | `/admin/convert-pending` | 批量转换 | `convert_pending_task` (新增) |

## 3. 端点详细规范

### 3.1 POST `/admin/documents/{document_id}/convert`

**功能**：触发单个文档的 MinerU/MarkItDown 转换，完成后状态变为 `CONVERTED`。

**请求**：

```http
POST /api/v1/admin/documents/{document_id}/convert
Content-Type: application/json

{
  "force": false
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `document_id` | path, UUID | ✅ | 文档 ID |
| `force` | body, bool | ❌ | `true` = 即使已 CONVERTED/COMPLETED 也强制重新转换（先重置为 UPLOADED）|

**前置条件**：

| 当前状态 | force=false | force=true |
|----------|------------|------------|
| UPLOADED | ✅ 触发转换 | ✅ 触发转换 |
| FAILED | ✅ 触发转换（重试）| ✅ 触发转换 |
| PENDING | ✅ 触发转换 | ✅ 触发转换 |
| PROCESSING | ❌ 409 Conflict | ❌ 409 Conflict |
| CONVERTED | ❌ 200 已完成 | ✅ 重置为 UPLOADED → 重新转换 |
| COMPLETED | ❌ 200 已完成 | ✅ 重置为 UPLOADED → 重新转换（删除旧索引）|

**成功响应** (202 Accepted)：

```json
{
  "message": "Conversion queued",
  "document_id": "c64a48d1-bb53-457d-8b89-e306b66de0c1",
  "previous_status": "uploaded",
  "target_status": "converted"
}
```

**错误响应**：

| 状态码 | 场景 |
|--------|------|
| 404 | 文档不存在 |
| 409 | 文档正在处理中 |

### 3.2 POST `/admin/documents/{document_id}/index`

**功能**：对已转换文档执行 RAG 分块 + pgvector 索引 + ES 索引，完成后状态变为 `COMPLETED`。

**请求**：

```http
POST /api/v1/admin/documents/{document_id}/index
Content-Type: application/json

{
  "force": false
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `document_id` | path, UUID | ✅ | 文档 ID |
| `force` | body, bool | ❌ | `true` = 即使已 COMPLETED 也强制重建索引（先删除旧索引 + 重置为 CONVERTED）|

**前置条件**：

| 当前状态 | force=false | force=true |
|----------|------------|------------|
| CONVERTED | ✅ 触发索引 | ✅ 触发索引 |
| COMPLETED | ❌ 200 已完成 | ✅ 删除旧索引 → 重置 CONVERTED → 重新索引 |
| FAILED (有 content_path) | ✅ 重置 CONVERTED → 触发索引 | ✅ 同左 |
| FAILED (无 content_path) | ❌ 422 需要先转换 | ❌ 422 需要先转换 |
| UPLOADED | ❌ 422 需要先转换 | ❌ 422 需要先转换 |
| PROCESSING | ❌ 409 Conflict | ❌ 409 Conflict |

**成功响应** (202 Accepted)：

```json
{
  "message": "Indexing queued",
  "document_id": "c64a48d1-bb53-457d-8b89-e306b66de0c1",
  "previous_status": "converted",
  "target_status": "completed"
}
```

**错误响应**：

| 状态码 | 场景 | 错误信息 |
|--------|------|---------|
| 404 | 文档不存在 | Document not found |
| 409 | 文档正在处理中 | Document is currently processing |
| 422 | 文档未转换 | Document must be converted first (status: uploaded) |

### 3.3 POST `/admin/convert-pending`

**功能**：批量触发待转换文档的仅转换操作。支持指定 document_ids 过滤。

**请求**：

```http
POST /api/v1/admin/convert-pending
Content-Type: application/json

{
  "document_ids": ["uuid1", "uuid2"],
  "dry_run": false
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `document_ids` | body, list[UUID] | ❌ | 指定文档 ID 列表。为空或省略则处理所有 uploaded/failed 文档 |
| `dry_run` | body, bool | ❌ | `true` = 仅返回待转换列表，不触发任何处理 |

**成功响应** (200 OK)：

dry_run=true:
```json
{
  "pending_count": 3,
  "document_ids": ["uuid1", "uuid2", "uuid3"],
  "dry_run": true
}
```

dry_run=false:
```json
{
  "queued_count": 3,
  "document_ids": ["uuid1", "uuid2", "uuid3"],
  "skipped": [
    {
      "document_id": "uuid4",
      "reason": "status is completed"
    }
  ],
  "mode": "convert_only"
}
```

## 4. 现有端点变更

### 4.1 POST `/admin/reprocess-pending` — 保持不变

行为完全不变：触发所有 uploaded/failed/pending 文档的**完整流水线**。

### 4.2 POST `/admin/documents/{id}/reindex` — 行为增强

现有行为保持不变。但内部实现使用重构后的 `_process_document_async()`，会智能判断：
- 如果文档状态为 CONVERTED → 从索引阶段开始（跳过转换）
- 如果文档状态为 UPLOADED/FAILED → 完整流水线

### 4.3 GET `/library/documents` — 过滤条件扩展

已有的 `status` query 参数支持新增的 `converted` 值：

```http
GET /api/v1/library/documents?status=converted
```

### 4.4 GET `/admin/index-stats` — 统计扩展

在现有统计中新增 `converted` 状态计数：

```json
{
  "by_status": {
    "uploaded": 2,
    "pending": 0,
    "processing": 1,
    "converted": 3,
    "completed": 15,
    "failed": 0
  },
  "total": 21
}
```

## 5. Request/Response Schema

### 5.1 Pydantic Models

```python
# api/models.py

class ConvertDocumentRequest(BaseModel):
    force: bool = False

class IndexDocumentRequest(BaseModel):
    force: bool = False

class ConvertPendingRequest(BaseModel):
    document_ids: list[str] | None = None
    dry_run: bool = False

class DocumentOperationResponse(BaseModel):
    message: str
    document_id: str
    previous_status: str
    target_status: str

class ConvertPendingResponse(BaseModel):
    queued_count: int | None = None
    pending_count: int | None = None
    document_ids: list[str]
    skipped: list[dict] | None = None
    dry_run: bool = False
    mode: str | None = None
```

### 5.2 Router 实现样例

```python
# api/routers/admin.py

@router.post("/documents/{document_id}/convert", response_model=DocumentOperationResponse)
async def convert_document(
    document_id: str,
    request: ConvertDocumentRequest = ConvertDocumentRequest(),
    session: AsyncSession = Depends(get_session),
):
    """触发单文档转换（仅 MinerU/MarkItDown，不执行索引）。"""
    doc_repo = DocumentRepositoryImpl(session)
    document = await doc_repo.get(document_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status == DocumentStatus.PROCESSING:
        raise HTTPException(status_code=409, detail="Document is currently processing")
    
    if not request.force and document.status in (DocumentStatus.CONVERTED, DocumentStatus.COMPLETED):
        return DocumentOperationResponse(
            message="Document already converted",
            document_id=document_id,
            previous_status=document.status.value,
            target_status=document.status.value,
        )
    
    previous_status = document.status.value
    
    if request.force and document.status == DocumentStatus.COMPLETED:
        # 强制重转换：删除旧索引
        delete_document_nodes_task.delay(document_id)
    
    if request.force and document.status in (DocumentStatus.CONVERTED, DocumentStatus.COMPLETED):
        # 重置为 UPLOADED
        await doc_repo.update_status(
            document_id,
            status=DocumentStatus.UPLOADED,
            processing_stage=None,
            processing_meta=None,
            chunk_count=0,
        )
        await session.commit()
    
    # 触发转换
    convert_document_task.delay(document_id)
    
    return DocumentOperationResponse(
        message="Conversion queued",
        document_id=document_id,
        previous_status=previous_status,
        target_status="converted",
    )
```

## 6. Postman Collection 更新

新增以下请求到 Postman Collection 的 Admin 文件夹：

| 请求名 | 方法 | URL |
|--------|------|-----|
| Convert Document | POST | `{{api_base}}/admin/documents/{{document_id}}/convert` |
| Convert Document (Force) | POST | `{{api_base}}/admin/documents/{{document_id}}/convert` body: `{"force": true}` |
| Index Document | POST | `{{api_base}}/admin/documents/{{document_id}}/index` |
| Index Document (Force) | POST | `{{api_base}}/admin/documents/{{document_id}}/index` body: `{"force": true}` |
| Convert Pending (All) | POST | `{{api_base}}/admin/convert-pending` body: `{"dry_run": false}` |
| Convert Pending (Filtered) | POST | `{{api_base}}/admin/convert-pending` body: `{"document_ids": ["{{document_id}}"], "dry_run": false}` |
| Convert Pending (Dry Run) | POST | `{{api_base}}/admin/convert-pending` body: `{"dry_run": true}` |

## 7. 与现有端点的关系矩阵

| 操作 | 端点 | 执行阶段 | 终态 |
|------|------|---------|------|
| 单文档仅转换 | `POST /admin/documents/{id}/convert` | converting | CONVERTED |
| 单文档仅索引 | `POST /admin/documents/{id}/index` | splitting → indexing | COMPLETED |
| 单文档完整流水线 | `POST /admin/documents/{id}/reindex` | 所有阶段 | COMPLETED |
| 批量仅转换 | `POST /admin/convert-pending` | converting | CONVERTED |
| 批量完整流水线 | `POST /admin/reprocess-pending` | 所有阶段 | COMPLETED |
| Notebook 关联触发 | `POST /notebooks/{id}/documents` | 智能补齐 | COMPLETED |
