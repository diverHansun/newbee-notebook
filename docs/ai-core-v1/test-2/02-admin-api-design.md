# 管理接口设计

## 需求背景

运维和开发过程中需要以下管理能力:
- 手动触发处理pending文档
- 单文档索引重建
- 查看系统索引状态

## 接口设计

### 1. POST /api/v1/admin/reprocess-pending

批量处理所有pending状态的文档。

**请求**:

```http
POST /api/v1/admin/reprocess-pending
Content-Type: application/json

{
  "dry_run": false  // 可选，true时只返回待处理列表不执行
}
```

**响应**:

```json
{
  "queued_count": 4,
  "document_ids": [
    "22aea3cd-823a-4776-88bc-140029ab5328",
    "49c20f93-72f0-46ae-9bbb-a08baa62e803",
    "eba8cd61-3a7b-46d2-a914-c1c5bc8641cc",
    "c4c828e1-7c5c-45b5-b869-761739004384"
  ]
}
```

**实现逻辑**:
1. 查询documents表中status=pending的记录
2. 对每个document_id调用`process_document_task.delay()`
3. 返回已入队的文档列表

**复用现有代码**: `_process_all_pending_async()` in `document_tasks.py`

### 2. POST /api/v1/admin/documents/{id}/reindex

重建单个文档的索引(embedding + ES)。

**请求**:

```http
POST /api/v1/admin/documents/22aea3cd-823a-4776-88bc-140029ab5328/reindex
Content-Type: application/json

{
  "force": false  // 可选，true时即使status=completed也重建
}
```

**响应**:

```json
{
  "document_id": "22aea3cd-823a-4776-88bc-140029ab5328",
  "status": "queued",
  "message": "Reindex task queued"
}
```

**实现逻辑**:
1. 检查文档是否存在
2. 若`force=false`且status不为completed/failed，返回400
3. 调用`delete_document_nodes_task.delay(document_id)` 清理旧索引
4. 将status重置为processing
5. 调用`process_document_task.delay(document_id)` 重新处理

**与process的区别**:
- process: 提取文本 -> 分chunk -> 写embedding + ES
- reindex: 仅清理旧索引 -> 重新写embedding + ES (不重新提取文本)

**注意**: 当前实现中reindex等同于完整reprocess，若需仅重建索引需新增逻辑保存中间文本。

### 3. GET /api/v1/admin/index-stats

获取系统索引统计信息。

**请求**:

```http
GET /api/v1/admin/index-stats
```

**响应**:

```json
{
  "documents": {
    "total": 10,
    "by_status": {
      "pending": 2,
      "processing": 0,
      "completed": 7,
      "failed": 1
    }
  },
  "pgvector": {
    "table": "data_documents_biobert",
    "row_count": 1500,
    "unique_documents": 7
  },
  "elasticsearch": {
    "index": "medimind_docs",
    "doc_count": 1500
  }
}
```

**实现逻辑**:
1. 查询documents表按status分组统计
2. 查询pgvector表: `SELECT COUNT(*), COUNT(DISTINCT metadata_->>'document_id') FROM ...`
3. 调用ES API: `GET /medimind_docs/_count`

**用途**:
- 快速判断是否有pending积压
- 检查DB文档数与索引数是否一致
- 发现孤立索引数据

## 路由文件结构

新建 `medimind_agent/api/routers/admin.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/admin", tags=["Admin"])

class ReprocessResponse(BaseModel):
    queued_count: int
    document_ids: List[str]

class ReindexResponse(BaseModel):
    document_id: str
    status: str
    message: str

class IndexStats(BaseModel):
    documents: dict
    pgvector: dict
    elasticsearch: dict

@router.post("/reprocess-pending", response_model=ReprocessResponse)
async def reprocess_pending(dry_run: bool = False):
    ...

@router.post("/documents/{document_id}/reindex", response_model=ReindexResponse)
async def reindex_document(document_id: str, force: bool = False):
    ...

@router.get("/index-stats", response_model=IndexStats)
async def get_index_stats():
    ...
```

在`main.py`中注册:

```python
from medimind_agent.api.routers import admin
app.include_router(admin.router, prefix="/api/v1")
```

## 安全说明

当前设计无鉴权，仅适用于内网开发环境。生产环境需添加:
- API Key验证
- IP白名单
- 操作日志记录
