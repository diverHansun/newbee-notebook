# API 端点设计

## 1. 端点变更总览

### 1.1 废弃的端点

| 端点 | 方法 | 原功能 | 废弃原因 |
|------|------|--------|----------|
| `/documents/notebooks/{notebook_id}/upload` | POST | 直接上传到 Notebook | 强制 Library 优先模式 |

### 1.2 修改的端点

| 端点 | 方法 | 变更内容 |
|------|------|----------|
| `/documents/library/upload` | POST | 支持批量上传；仅保存文件，不触发处理 |
| `/documents/{document_id}` | DELETE | 增加完整清理逻辑（文件 + 向量 + 索引） |

### 1.3 新增的端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/notebooks/{notebook_id}/documents` | POST | 批量添加文档到 Notebook |
| `/notebooks/{notebook_id}/documents` | GET | 列出 Notebook 的文档 |
| `/notebooks/{notebook_id}/documents/{document_id}` | DELETE | 从 Notebook 移除文档 |
| `/documents/{document_id}/download` | GET | 下载原始文件 |

## 2. 详细设计

### 2.1 上传文档到 Library

**端点**：`POST /api/v1/documents/library/upload`

**描述**：批量上传文档到 Library，仅保存文件，不触发转换和 Embedding。

**请求**：
```
Content-Type: multipart/form-data
```

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| files | File[] | 是 | 上传的文件列表 |

**响应**：
```json
{
  "documents": [
    {
      "document_id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "医学影像分析.pdf",
      "status": "uploaded",
      "content_type": "pdf",
      "file_size": 1048576,
      "file_path": "550e8400-e29b-41d4-a716-446655440000/original/医学影像分析.pdf",
      "created_at": "2026-02-07T10:00:00Z"
    }
  ],
  "total": 1,
  "failed": []
}
```

**状态码**：
| 状态码 | 描述 |
|--------|------|
| 201 | 上传成功 |
| 400 | 文件类型不支持 |
| 413 | 文件过大 |

**业务逻辑**：
```
1. 验证文件类型（pdf, docx, xlsx, csv, md, txt）
2. 验证文件大小（不超过配置限制）
3. 为每个文件生成 document_id
4. 创建目录 {document_id}/original/
5. 保存文件（保留原始文件名）
6. 创建 Document 记录（status=UPLOADED）
7. 返回文档列表
```

---

### 2.2 添加文档到 Notebook

**端点**：`POST /api/v1/notebooks/{notebook_id}/documents`

**描述**：将 Library 中的文档添加到 Notebook，触发转换和 Embedding 处理。

**路径参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| notebook_id | UUID | Notebook ID |

**请求体**：
```json
{
  "document_ids": [
    "550e8400-e29b-41d4-a716-446655440000",
    "550e8400-e29b-41d4-a716-446655440001"
  ]
}
```

**响应**：
```json
{
  "notebook_id": "660e8400-e29b-41d4-a716-446655440000",
  "added": [
    {
      "document_id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "医学影像分析.pdf",
      "status": "processing"
    }
  ],
  "skipped": [
    {
      "document_id": "550e8400-e29b-41d4-a716-446655440001",
      "reason": "already_added"
    }
  ],
  "failed": [
    {
      "document_id": "550e8400-e29b-41d4-a716-446655440002",
      "reason": "document_not_found"
    }
  ]
}
```

**状态码**：
| 状态码 | 描述 |
|--------|------|
| 200 | 操作完成（部分成功也返回 200） |
| 404 | Notebook 不存在 |

**业务逻辑**：
```
1. 验证 Notebook 存在
2. 对每个 document_id：
   a. 验证文档存在且属于 Library
   b. 检查是否已添加（跳过重复）
   c. 创建 NotebookDocumentRef 记录
   d. 如果文档 status=UPLOADED，创建处理任务
3. 返回处理结果
```

---

### 2.3 列出 Notebook 文档

**端点**：`GET /api/v1/notebooks/{notebook_id}/documents`

**描述**：列出 Notebook 关联的所有文档。

**路径参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| notebook_id | UUID | Notebook ID |

**查询参数**：
| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| limit | int | 20 | 每页数量 |
| offset | int | 0 | 偏移量 |
| status | string | - | 按状态过滤（uploaded, processing, completed, failed） |

**响应**：
```json
{
  "data": [
    {
      "document_id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "医学影像分析.pdf",
      "status": "completed",
      "content_type": "pdf",
      "file_size": 1048576,
      "page_count": 50,
      "chunk_count": 120,
      "added_at": "2026-02-07T10:30:00Z",
      "created_at": "2026-02-07T10:00:00Z"
    }
  ],
  "pagination": {
    "total": 1,
    "limit": 20,
    "offset": 0
  }
}
```

**状态码**：
| 状态码 | 描述 |
|--------|------|
| 200 | 成功 |
| 404 | Notebook 不存在 |

---

### 2.4 从 Notebook 移除文档

**端点**：`DELETE /api/v1/notebooks/{notebook_id}/documents/{document_id}`

**描述**：从 Notebook 移除文档关联，不删除原文档和向量数据。

**路径参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| notebook_id | UUID | Notebook ID |
| document_id | UUID | Document ID |

**响应**：无内容

**状态码**：
| 状态码 | 描述 |
|--------|------|
| 204 | 移除成功 |
| 404 | Notebook 或关联不存在 |

**业务逻辑**：
```
1. 验证 Notebook 存在
2. 验证关联存在
3. 删除 NotebookDocumentRef 记录
4. 不删除 Document、向量、文件
```

---

### 2.5 下载原始文件

**端点**：`GET /api/v1/documents/{document_id}/download`

**描述**：下载文档的原始文件。

**路径参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| document_id | UUID | Document ID |

**响应**：
```
Content-Type: application/octet-stream
Content-Disposition: attachment; filename="原始文件名.pdf"
```

**状态码**：
| 状态码 | 描述 |
|--------|------|
| 200 | 成功 |
| 404 | 文档不存在或文件不存在 |

---

### 2.6 删除文档（完整删除）

**端点**：`DELETE /api/v1/documents/{document_id}`

**描述**：从 Library 完全删除文档，包括所有关联数据。

**路径参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| document_id | UUID | Document ID |

**查询参数**：
| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| force | bool | false | 强制删除（即使有 Notebook 引用） |

**响应**：
```json
{
  "message": "Document deleted",
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "cleaned": {
    "files": true,
    "vectors": true,
    "elasticsearch": true,
    "references_removed": 2
  }
}
```

**状态码**：
| 状态码 | 描述 |
|--------|------|
| 200 | 删除成功 |
| 404 | 文档不存在 |
| 409 | 有 Notebook 引用且 force=false |

**业务逻辑**：
```
1. 验证文档存在
2. 检查 Notebook 引用
   - 有引用且 force=false：返回 409
   - 有引用且 force=true：继续删除
3. 删除所有 NotebookDocumentRef
4. 异步删除向量数据（pgvector + ES）
5. 同步删除文件系统 {document_id}/ 目录
6. 删除 Document 数据库记录
7. 返回清理结果
```

---

## 3. 完整端点列表

### 3.1 Library

| 端点 | 方法 | 描述 |
|------|------|------|
| `/library` | GET | 获取 Library 信息 |
| `/library/documents` | GET | 列出 Library 文档 |

### 3.2 Documents

| 端点 | 方法 | 描述 |
|------|------|------|
| `/documents/library/upload` | POST | 批量上传到 Library |
| `/documents/{id}` | GET | 获取文档详情 |
| `/documents/{id}` | DELETE | 完全删除文档 |
| `/documents/{id}/content` | GET | 获取转换后内容 |
| `/documents/{id}/download` | GET | 下载原始文件 |

### 3.3 Notebooks

| 端点 | 方法 | 描述 |
|------|------|------|
| `/notebooks` | POST | 创建 Notebook |
| `/notebooks` | GET | 列出 Notebooks |
| `/notebooks/{id}` | GET | 获取 Notebook |
| `/notebooks/{id}` | PATCH | 更新 Notebook |
| `/notebooks/{id}` | DELETE | 删除 Notebook |
| `/notebooks/{id}/documents` | POST | 添加文档到 Notebook |
| `/notebooks/{id}/documents` | GET | 列出 Notebook 文档 |
| `/notebooks/{id}/documents/{doc_id}` | DELETE | 从 Notebook 移除文档 |

### 3.4 Sessions

| 端点 | 方法 | 描述 |
|------|------|------|
| `/notebooks/{id}/sessions` | POST | 创建 Session |
| `/notebooks/{id}/sessions` | GET | 列出 Sessions |
| `/notebooks/{id}/sessions/latest` | GET | 获取最新 Session |
| `/sessions/{id}` | GET | 获取 Session |
| `/sessions/{id}` | DELETE | 删除 Session |

### 3.5 Chat

| 端点 | 方法 | 描述 |
|------|------|------|
| `/chat/notebooks/{id}/chat` | POST | 非流式聊天 |
| `/chat/notebooks/{id}/chat/stream` | POST | 流式聊天 |
| `/chat/stream/{message_id}/cancel` | POST | 取消流式 |

### 3.6 Admin

| 端点 | 方法 | 描述 |
|------|------|------|
| `/admin/reprocess-pending` | POST | 重处理 pending 文档 |
| `/admin/documents/{id}/reindex` | POST | 重建索引 |
| `/admin/index-stats` | GET | 索引统计 |

### 3.7 废弃

| 端点 | 方法 | 状态 |
|------|------|------|
| `/documents/notebooks/{id}/upload` | POST | 废弃 |
