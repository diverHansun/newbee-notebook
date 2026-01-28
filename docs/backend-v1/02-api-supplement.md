# API补充设计

## 1. 概述

本文档描述MediMind Agent需要新增的API接口,主要用于支持前端文档阅读器功能。

---

## 2. 现有API概览

### 2.1 Documents路由 (已有)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /documents/library | 注册文档到Library |
| POST | /documents/notebooks/{id} | 注册文档到Notebook |
| POST | /documents/library/upload | 上传文件到Library |
| POST | /documents/notebooks/{id}/upload | 上传文件到Notebook |
| GET | /documents/{id} | 获取文档元数据 |
| GET | /documents/library | 列出Library文档 |
| GET | /documents/notebooks/{id} | 列出Notebook文档 |
| DELETE | /documents/{id} | 删除文档 |

### 2.2 缺失的接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /documents/{id}/content | 获取文档内容(用于阅读器) |
| GET | /documents/{id}/download | 下载原始文件 |

---

## 3. 新增接口设计

### 3.1 获取文档内容

#### 接口定义

```
GET /api/v1/documents/{document_id}/content
```

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| document_id | string (path) | 是 | 文档ID |
| format | string (query) | 否 | 返回格式: markdown/text, 默认markdown |

#### 响应

```json
{
  "document_id": "uuid",
  "title": "文档标题",
  "content_type": "pdf",
  "format": "markdown",
  "content": "# 标题\n\n文档内容...",
  "page_count": 10,
  "chunk_count": 25,
  "original_file_available": true,
  "download_url": "/api/v1/documents/{id}/download"
}
```

#### 响应说明

| 字段 | 类型 | 说明 |
|------|------|------|
| content | string | Markdown或纯文本内容 |
| format | string | 实际返回的格式 |
| original_file_available | boolean | 原始文件是否可下载 |
| download_url | string | 原始文件下载链接(Excel/CSV等) |

#### 实现代码

```python
# api/routers/documents.py

@router.get("/{document_id}/content")
async def get_document_content(
    document_id: str,
    format: str = Query("markdown", enum=["markdown", "text"]),
    service: DocumentService = Depends(get_document_service),
):
    """获取文档内容,用于前端阅读器展示"""
    doc = await service.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status != DocumentStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Document not ready, status: {doc.status.value}"
        )

    # 根据格式返回内容
    if format == "markdown" and doc.content_markdown:
        content = doc.content_markdown
        actual_format = "markdown"
    else:
        content = doc.content_text or ""
        actual_format = "text"

    # 判断是否有原始文件可下载
    original_available = doc.content_type in [
        DocumentType.XLSX,
        DocumentType.XLS,
        DocumentType.CSV,
    ]

    return {
        "document_id": doc.document_id,
        "title": doc.title,
        "content_type": doc.content_type.value,
        "format": actual_format,
        "content": content,
        "page_count": doc.page_count,
        "chunk_count": doc.chunk_count,
        "original_file_available": original_available,
        "download_url": f"/api/v1/documents/{document_id}/download" if original_available else None,
    }
```

### 3.2 下载原始文件

#### 接口定义

```
GET /api/v1/documents/{document_id}/download
```

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| document_id | string (path) | 是 | 文档ID |

#### 响应

文件流 (Content-Type根据文件类型)

#### 实现代码

```python
# api/routers/documents.py

from fastapi.responses import FileResponse
import os

@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    service: DocumentService = Depends(get_document_service),
):
    """下载文档原始文件"""
    doc = await service.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="File not found on server")

    # 获取文件名
    filename = os.path.basename(doc.file_path)

    # 设置Content-Type
    content_type_map = {
        DocumentType.PDF: "application/pdf",
        DocumentType.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        DocumentType.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        DocumentType.XLS: "application/vnd.ms-excel",
        DocumentType.CSV: "text/csv",
        DocumentType.TXT: "text/plain",
        DocumentType.MD: "text/markdown",
    }
    media_type = content_type_map.get(doc.content_type, "application/octet-stream")

    return FileResponse(
        path=doc.file_path,
        filename=filename,
        media_type=media_type,
    )
```

---

## 4. 响应模型

### 4.1 新增响应模型

```python
# api/models/responses.py

class DocumentContentResponse(BaseModel):
    document_id: str
    title: str
    content_type: str
    format: str
    content: str
    page_count: int
    chunk_count: int
    original_file_available: bool
    download_url: Optional[str] = None
```

---

## 5. 错误处理

### 5.1 错误码

| HTTP状态码 | 场景 | 响应 |
|------------|------|------|
| 404 | 文档不存在 | {"detail": "Document not found"} |
| 400 | 文档未处理完成 | {"detail": "Document not ready, status: processing"} |
| 404 | 原始文件不存在 | {"detail": "File not found on server"} |

---

## 6. Postman Collection补充

```json
{
  "name": "Documents",
  "item": [
    {
      "name": "Get Document Content",
      "request": {
        "method": "GET",
        "url": {
          "raw": "{{api_base}}/documents/{{document_id}}/content?format=markdown",
          "query": [
            {"key": "format", "value": "markdown"}
          ]
        }
      }
    },
    {
      "name": "Download Document",
      "request": {
        "method": "GET",
        "url": "{{api_base}}/documents/{{document_id}}/download"
      }
    }
  ]
}
```

---

## 7. 前端调用示例

### 7.1 获取文档内容

```typescript
// lib/api/documents.ts

export async function getDocumentContent(documentId: string): Promise<DocumentContent> {
  const response = await fetch(
    `/api/v1/documents/${documentId}/content?format=markdown`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    throw new Error('Failed to fetch document content');
  }

  return response.json();
}
```

### 7.2 下载原始文件

```typescript
// lib/api/documents.ts

export function getDocumentDownloadUrl(documentId: string): string {
  return `/api/v1/documents/${documentId}/download`;
}

// 使用
<a href={getDocumentDownloadUrl(doc.document_id)} download>
  下载原始文件
</a>
```

---

## 8. 安全考虑

1. 权限验证: 确保用户只能访问其有权限的文档
2. 路径遍历防护: file_path不应来自用户输入
3. 文件大小限制: 大文件考虑分页返回或流式传输
4. 缓存: 对于不变的文档内容,可添加缓存头
