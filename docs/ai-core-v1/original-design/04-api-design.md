# AI Core v1 API 接口设计

## 1. API 设计原则

### 1.1 RESTful 风格

- 使用名词表示资源
- 使用 HTTP 方法表示操作
- URL 层级表达资源关系
- 使用标准 HTTP 状态码

### 1.2 版本控制

- URL 路径版本：/api/v1/
- 向后兼容承诺
- 弃用策略：保留至少两个大版本

### 1.3 响应格式

- 统一 JSON 格式
- 成功返回数据或数据列表
- 失败返回错误对象
- 时间使用 ISO 8601 格式

## 2. 通用约定

### 2.1 请求头

```
Content-Type: application/json
Accept: application/json
X-Request-ID: {uuid}  (可选，用于追踪)
```

### 2.2 响应头

```
Content-Type: application/json
X-Request-ID: {uuid}
X-Response-Time: {ms}
```

### 2.3 分页

使用 limit 和 offset 参数：
- limit：每页数量，默认 20，最大 100
- offset：偏移量，默认 0

响应包含分页信息：
- total：总数
- limit：每页数量
- offset：当前偏移

### 2.4 过滤和排序

- 过滤：使用查询参数，如 ?status=completed
- 排序：使用 sort 参数，如 ?sort=-created_at（降序）

### 2.5 错误响应

统一错误格式：

```json
{
    "error_code": "E3001",
    "message": "该 Notebook 已达到 Session 上限（20 个）",
    "details": {
        "current_count": 20,
        "max_count": 20,
        "suggestions": [
            "删除不需要的 Session",
            "创建新的 Notebook"
        ]
    }
}
```

错误码格式：`Exxxx`（详见 [08-error-handling.md](08-error-handling.md)）

### 2.6 分页响应格式

分页接口使用嵌套的 pagination 对象：

```json
{
    "data": [...],
    "pagination": {
        "total": 100,
        "limit": 20,
        "offset": 0,
        "has_next": true,
        "has_prev": false
    }
}
```

## 3. Library 接口

### 3.1 获取 Library 信息

**请求**
```
GET /api/v1/library
```

**响应**
```json
{
  "library_id": "uuid",
  "document_count": 10,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### 3.2 获取 Library 文档列表

**请求**
```
GET /api/v1/library/documents?limit=20&offset=0&status=completed
```

**响应**
```json
{
  "total": 50,
  "limit": 20,
  "offset": 0,
  "documents": [
    {
      "document_id": "doc-1",
      "title": "论文标题",
      "content_type": "pdf",
      "status": "completed",
      "page_count": 10,
      "chunk_count": 50,
      "reference_count": 2,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 3.3 上传文档到 Library

**请求（文件上传）**
```
POST /api/v1/library/documents/upload
Content-Type: multipart/form-data

file: <binary>
title: "论文标题"  (可选)
```

**请求（URL 上传）**
```
POST /api/v1/library/documents/upload
Content-Type: application/json

{
  "url": "https://youtube.com/watch?v=xxx",
  "title": "视频标题"
}
```

**响应**
```json
{
  "document_id": "doc-1",
  "title": "论文标题",
  "status": "processing",
  "created_at": "2024-01-01T00:00:00Z",
  "estimated_time": 30
}
```

### 3.4 删除 Library 文档

**请求**
```
DELETE /api/v1/library/documents/{document_id}
```

**响应（无引用）**
```
HTTP/1.1 204 No Content
```

**响应（有引用，需确认）**
```json
{
  "error_code": "DOCUMENT_REFERENCED",
  "message": "该文档被 2 个 Notebook 引用",
  "details": {
    "reference_count": 2,
    "notebooks": ["Notebook A", "Notebook B"],
    "confirm_required": true
  }
}
```

### 3.5 确认删除被引用的文档

**请求**
```
DELETE /api/v1/library/documents/{document_id}?confirm=true
```

**响应**
```
HTTP/1.1 204 No Content
```

## 4. Notebook 接口

### 4.1 创建 Notebook

**请求**
```
POST /api/v1/notebooks
Content-Type: application/json

{
  "title": "医学研究笔记",
  "description": "关于心血管疾病的研究资料"
}
```

**响应**
```json
{
  "notebook_id": "uuid",
  "title": "医学研究笔记",
  "description": "关于心血管疾病的研究资料",
  "session_count": 0,
  "document_count": 0,
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 4.2 获取 Notebook 列表

**请求**
```
GET /api/v1/notebooks?limit=20&offset=0&sort=-updated_at
```

**响应**
```json
{
  "total": 5,
  "limit": 20,
  "offset": 0,
  "notebooks": [
    {
      "notebook_id": "uuid",
      "title": "医学研究笔记",
      "description": "关于心血管疾病的研究资料",
      "session_count": 3,
      "document_count": 5,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-02T00:00:00Z"
    }
  ]
}
```

### 4.3 获取 Notebook 详情

**请求**
```
GET /api/v1/notebooks/{notebook_id}
```

**响应**
```json
{
  "notebook_id": "uuid",
  "title": "医学研究笔记",
  "description": "关于心血管疾病的研究资料",
  "session_count": 3,
  "document_count": 5,
  "documents": [
    {
      "document_id": "doc-1",
      "title": "论文标题",
      "content_type": "pdf",
      "source": "notebook",
      "status": "completed"
    },
    {
      "document_id": "doc-2",
      "title": "参考资料",
      "content_type": "docx",
      "source": "library",
      "reference_id": "ref-1",
      "status": "completed"
    }
  ],
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-02T00:00:00Z"
}
```

### 4.4 更新 Notebook

**请求**
```
PATCH /api/v1/notebooks/{notebook_id}
Content-Type: application/json

{
  "title": "新标题",
  "description": "新描述"
}
```

**响应**
```json
{
  "notebook_id": "uuid",
  "title": "新标题",
  "description": "新描述",
  "updated_at": "2024-01-02T00:00:00Z"
}
```

### 4.5 删除 Notebook

删除 Notebook 及其专属文档、所有 Session。

**请求**
```
DELETE /api/v1/notebooks/{notebook_id}
```

**响应**
```
HTTP/1.1 204 No Content
```

### 4.6 上传文档到 Notebook

**请求（文件上传）**
```
POST /api/v1/notebooks/{notebook_id}/documents/upload
Content-Type: multipart/form-data

file: <binary>
title: "论文标题"
```

**请求（URL 上传）**
```
POST /api/v1/notebooks/{notebook_id}/documents/upload
Content-Type: application/json

{
  "url": "https://youtube.com/watch?v=xxx",
  "title": "视频标题"
}
```

**响应**
```json
{
  "document_id": "doc-1",
  "notebook_id": "uuid",
  "title": "论文标题",
  "status": "processing",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 4.7 从 Library 引用文档到 Notebook

**请求**
```
POST /api/v1/notebooks/{notebook_id}/references
Content-Type: application/json

{
  "document_id": "doc-1"
}
```

**响应**
```json
{
  "reference_id": "ref-1",
  "notebook_id": "uuid",
  "document_id": "doc-1",
  "document_title": "论文标题",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 4.8 取消文档引用

**请求**
```
DELETE /api/v1/notebooks/{notebook_id}/references/{reference_id}
```

**响应**
```
HTTP/1.1 204 No Content
```

### 4.9 获取 Notebook 文档列表

获取 Notebook 内所有文档（包括直接上传的 + 从 Library 引用的）。

**请求**
```
GET /api/v1/notebooks/{notebook_id}/documents
```

**响应**
```json
{
  "notebook_id": "uuid",
  "total": 5,
  "documents": [
    {
      "document_id": "doc-1",
      "title": "直接上传的文档",
      "content_type": "pdf",
      "source": "notebook",
      "status": "completed"
    },
    {
      "document_id": "doc-2",
      "title": "引用的文档",
      "content_type": "docx",
      "source": "library",
      "reference_id": "ref-1",
      "status": "completed"
    }
  ]
}
```

## 5. Session 接口

### 5.1 创建 Session

每个 Notebook 最多 20 个 Session。

**请求**
```
POST /api/v1/notebooks/{notebook_id}/sessions
Content-Type: application/json

{
  "title": "对话主题"
}
```

**响应（成功）**
```json
{
  "session_id": "uuid",
  "notebook_id": "uuid",
  "title": "对话主题",
  "message_count": 0,
  "created_at": "2024-01-01T00:00:00Z"
}
```

**响应（达到上限）**
```json
{
  "error_code": "SESSION_LIMIT_EXCEEDED",
  "message": "该 Notebook 已达到 Session 上限（20 个）",
  "details": {
    "current_count": 20,
    "max_count": 20,
    "suggestions": [
      "删除不需要的 Session",
      "创建新的 Notebook"
    ]
  }
}
```

### 5.2 获取 Session 列表

**请求**
```
GET /api/v1/notebooks/{notebook_id}/sessions?limit=20&offset=0
```

**响应**
```json
{
  "notebook_id": "uuid",
  "total": 5,
  "limit": 20,
  "offset": 0,
  "sessions": [
    {
      "session_id": "uuid",
      "title": "对话主题",
      "message_count": 10,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-02T00:00:00Z"
    }
  ]
}
```

### 5.3 获取最近 Session

打开 Notebook 时默认恢复最近的 Session。

**请求**
```
GET /api/v1/notebooks/{notebook_id}/sessions/latest
```

**响应（有 Session）**
```json
{
  "session_id": "uuid",
  "notebook_id": "uuid",
  "title": "对话主题",
  "message_count": 10,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-02T00:00:00Z"
}
```

**响应（无 Session）**
```json
{
  "session": null,
  "message": "该 Notebook 暂无 Session，请创建新的 Session"
}
```

### 5.4 获取 Session 详情

**请求**
```
GET /api/v1/sessions/{session_id}
```

**响应**
```json
{
  "session_id": "uuid",
  "notebook_id": "uuid",
  "title": "对话主题",
  "message_count": 10,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-02T00:00:00Z"
}
```

### 5.5 获取 Session 消息历史

**请求**
```
GET /api/v1/sessions/{session_id}/messages?limit=20&offset=0
```

**响应**
```json
{
  "session_id": "uuid",
  "total": 50,
  "limit": 20,
  "offset": 0,
  "messages": [
    {
      "id": 1,
      "role": "user",
      "content": "你好",
      "mode": "chat",
      "created_at": "2024-01-01T00:00:00Z"
    },
    {
      "id": 2,
      "role": "assistant",
      "content": "你好！有什么可以帮你的吗？",
      "mode": "chat",
      "sources": [],
      "created_at": "2024-01-01T00:00:01Z"
    }
  ]
}
```

### 5.6 删除 Session

**请求**
```
DELETE /api/v1/sessions/{session_id}
```

**响应**
```
HTTP/1.1 204 No Content
```

## 6. 对话接口

### 6.1 发送消息（非流式）

**请求**
```
POST /api/v1/notebooks/{notebook_id}/chat
Content-Type: application/json

{
  "session_id": "uuid",
  "message": "什么是RAG？",
  "mode": "ask"
}
```

**响应**
```json
{
  "message_id": 3,
  "content": "RAG是检索增强生成...",
  "mode": "ask",
  "sources": [
    {
      "document_id": "doc-1",
      "document_title": "论文标题",
      "chunk_id": "chunk-1",
      "content": "...",
      "page_number": 5
    }
  ],
  "created_at": "2024-01-01T02:00:00Z"
}
```

### 6.2 发送消息（流式）

**请求**
```
POST /api/v1/notebooks/{notebook_id}/chat/stream
Content-Type: application/json

{
  "session_id": "uuid",
  "message": "什么是RAG？",
  "mode": "ask"
}
```

**响应（Server-Sent Events）**
```
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache

data: {"type": "start", "message_id": 3}

data: {"type": "content", "delta": "RAG"}

data: {"type": "content", "delta": "是"}

data: {"type": "content", "delta": "检索增强生成"}

data: {"type": "sources", "sources": [{"document_id": "doc-1", ...}]}

data: {"type": "done"}

```

### 6.3 Explain 模式（文档选中触发）

用户在文档阅读器中选中文本，右键选择"讲解"。

**请求**
```
POST /api/v1/notebooks/{notebook_id}/chat/stream
Content-Type: application/json

{
  "session_id": "uuid",
  "mode": "explain",
  "context": {
    "selected_text": "RAG (Retrieval-Augmented Generation)",
    "document_id": "doc-1",
    "chunk_id": "chunk-5",
    "page_number": 3
  }
}
```

**响应（流式）**
```
data: {"type": "start", "message_id": 4}

data: {"type": "content", "delta": "RAG（检索增强生成）是一种..."}

data: {"type": "done"}
```

### 6.4 Conclude 模式（文档选中触发）

用户在文档阅读器中选中文本，右键选择"总结"。

**请求**
```
POST /api/v1/notebooks/{notebook_id}/chat/stream
Content-Type: application/json

{
  "session_id": "uuid",
  "mode": "conclude",
  "context": {
    "selected_text": "本研究通过对1000名患者的随访调查...",
    "document_id": "doc-1",
    "chunk_id": "chunk-10",
    "page_number": 5
  }
}
```

**响应（流式）**
```
data: {"type": "start", "message_id": 5}

data: {"type": "content", "delta": "这段内容的核心要点如下..."}

data: {"type": "done"}
```

### 6.5 SSE 事件类型

| 事件类型 | 说明 | 示例 |
|---------|------|------|
| start | 开始响应 | `{"type": "start", "message_id": 3}` |
| content | 内容增量 | `{"type": "content", "delta": "文本"}` |
| sources | 引用来源 | `{"type": "sources", "sources": [...]}` |
| done | 完成 | `{"type": "done"}` |
| error | 错误 | `{"type": "error", "error_code": "E6000", "message": "..."}` |
| heartbeat | 心跳保活 | `{"type": "heartbeat"}` |

**心跳机制**：
- 间隔：15 秒
- 超时：120 秒无输出则超时

### 6.6 中断流式输出

**请求**
```
POST /api/v1/chat/stream/{message_id}/cancel
```

**响应**
```json
{
  "message_id": 3,
  "status": "cancelled"
}
```

## 7. 搜索接口

### 7.1 在 Notebook 范围内搜索

**请求**
```
POST /api/v1/notebooks/{notebook_id}/search
Content-Type: application/json

{
  "query": "什么是RAG",
  "mode": "hybrid",
  "top_k": 10
}
```

**响应**
```json
{
  "notebook_id": "uuid",
  "query": "什么是RAG",
  "results": [
    {
      "chunk_id": "chunk-1",
      "document_id": "doc-1",
      "document_title": "论文标题",
      "content": "RAG是检索增强生成...",
      "score": 0.95,
      "page_number": 5,
      "section_title": "第二章 方法",
      "highlights": ["RAG", "检索增强生成"]
    }
  ],
  "total": 1
}
```

## 8. 文档内容接口

### 8.1 获取文档状态

**请求**
```
GET /api/v1/documents/{document_id}/status
```

**响应**
```json
{
  "document_id": "doc-1",
  "title": "论文标题",
  "status": "completed",
  "progress": 100,
  "created_at": "2024-01-01T00:00:00Z",
  "completed_at": "2024-01-01T00:00:30Z",
  "error": null
}
```

### 8.2 获取文档信息

**请求**
```
GET /api/v1/documents/{document_id}
```

**响应**
```json
{
  "document_id": "doc-1",
  "title": "论文标题",
  "content_type": "pdf",
  "file_path": "/path/to/file.pdf",
  "url": null,
  "status": "completed",
  "page_count": 10,
  "chunk_count": 50,
  "library_id": "uuid",
  "notebook_id": null,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:30Z"
}
```

### 8.3 获取文档结构化内容

**请求**
```
GET /api/v1/documents/{document_id}/content
```

**响应**
```json
{
  "document_id": "doc-1",
  "title": "论文标题",
  "structure": [
    {
      "type": "chapter",
      "title": "第一章 引言",
      "level": 1,
      "page_number": 1,
      "start_position": 0,
      "end_position": 1000,
      "children": [
        {
          "type": "section",
          "title": "1.1 背景",
          "level": 2,
          "page_number": 1,
          "start_position": 0,
          "end_position": 500
        }
      ]
    }
  ],
  "total_pages": 10
}
```

### 8.4 获取文档分块列表

**请求**
```
GET /api/v1/documents/{document_id}/chunks?page=1
```

**响应**
```json
{
  "document_id": "doc-1",
  "total_chunks": 50,
  "chunks": [
    {
      "chunk_id": "chunk-1",
      "content": "这是第一块内容...",
      "page_number": 1,
      "section_title": "第一章 引言",
      "section_level": 1,
      "start_position": 0,
      "end_position": 500
    }
  ]
}
```

### 8.5 删除 Notebook 专属文档

**请求**
```
DELETE /api/v1/notebooks/{notebook_id}/documents/{document_id}
```

**响应**
```
HTTP/1.1 204 No Content
```

## 9. 引用管理接口

### 9.1 创建引用

**请求**
```
POST /api/v1/references
Content-Type: application/json

{
  "session_id": "uuid",
  "chunk_id": "chunk-1",
  "document_id": "doc-1",
  "quoted_text": "RAG是检索增强生成"
}
```

**响应**
```json
{
  "reference_id": "ref-1",
  "session_id": "uuid",
  "chunk_id": "chunk-1",
  "document_id": "doc-1",
  "document_title": "论文标题",
  "quoted_text": "RAG是检索增强生成",
  "page_number": 5,
  "section_title": "第二章 方法",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 9.2 获取 Session 引用列表

**请求**
```
GET /api/v1/sessions/{session_id}/references
```

**响应**
```json
{
  "session_id": "uuid",
  "total": 5,
  "references": [
    {
      "reference_id": "ref-1",
      "document_id": "doc-1",
      "document_title": "论文标题",
      "quoted_text": "RAG是检索增强生成",
      "page_number": 5,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 9.3 获取引用详情

**请求**
```
GET /api/v1/references/{reference_id}
```

**响应**
```json
{
  "reference_id": "ref-1",
  "session_id": "uuid",
  "message_id": 3,
  "chunk_id": "chunk-1",
  "document_id": "doc-1",
  "document_title": "论文标题",
  "quoted_text": "RAG是检索增强生成",
  "context": "...RAG是检索增强生成...",
  "page_number": 5,
  "section_title": "第二章 方法",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 9.4 删除引用

**请求**
```
DELETE /api/v1/references/{reference_id}
```

**响应**
```
HTTP/1.1 204 No Content
```

## 10. 健康检查和监控

### 10.1 健康检查

**请求**
```
GET /health
```

**响应**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:00:00Z",
  "services": {
    "database": "healthy",
    "redis": "healthy",
    "elasticsearch": "healthy",
    "celery": "healthy"
  }
}
```

### 10.2 系统信息

**请求**
```
GET /api/v1/info
```

**响应**
```json
{
  "version": "1.0.0",
  "supported_formats": ["pdf", "docx", "xlsx", "youtube", "bilibili"],
  "max_file_size": 104857600,
  "supported_modes": ["chat", "ask", "conclude", "explain"],
  "session_limit_per_notebook": 20
}
```

## 11. 错误处理

### 11.1 错误码定义

| HTTP 状态码 | 错误码 | 说明 |
|------------|--------|------|
| 400 | INVALID_REQUEST | 请求参数无效 |
| 404 | NOT_FOUND | 资源不存在 |
| 409 | CONFLICT | 资源冲突 |
| 409 | SESSION_LIMIT_EXCEEDED | Session 数量达到上限 |
| 409 | DOCUMENT_REFERENCED | 文档被引用，需确认删除 |
| 413 | PAYLOAD_TOO_LARGE | 文件过大 |
| 422 | UNPROCESSABLE_ENTITY | 无法处理的实体 |
| 500 | INTERNAL_ERROR | 服务器内部错误 |
| 503 | SERVICE_UNAVAILABLE | 服务不可用 |

### 11.2 错误响应示例

**Session 达到上限**
```json
{
  "error_code": "SESSION_LIMIT_EXCEEDED",
  "message": "该 Notebook 已达到 Session 上限（20 个）",
  "details": {
    "current_count": 20,
    "max_count": 20,
    "suggestions": [
      "删除不需要的 Session",
      "创建新的 Notebook"
    ]
  }
}
```

**文档被引用**
```json
{
  "error_code": "DOCUMENT_REFERENCED",
  "message": "该文档被 2 个 Notebook 引用",
  "details": {
    "reference_count": 2,
    "notebooks": ["Notebook A", "Notebook B"],
    "confirm_required": true
  }
}
```

**请求参数无效**
```json
{
  "error_code": "INVALID_REQUEST",
  "message": "参数 'mode' 必须是以下之一: chat, ask, conclude, explain",
  "details": {
    "field": "mode",
    "provided": "invalid_mode"
  }
}
```

**资源不存在**
```json
{
  "error_code": "NOT_FOUND",
  "message": "Notebook 不存在",
  "details": {
    "notebook_id": "invalid-uuid"
  }
}
```

## 12. 接口总览

### 12.1 Library 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/library | 获取 Library 信息 |
| GET | /api/v1/library/documents | 获取文档列表 |
| POST | /api/v1/library/documents/upload | 上传文档 |
| DELETE | /api/v1/library/documents/{id} | 删除文档 |

### 12.2 Notebook 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/notebooks | 创建 Notebook |
| GET | /api/v1/notebooks | 获取列表 |
| GET | /api/v1/notebooks/{id} | 获取详情 |
| PATCH | /api/v1/notebooks/{id} | 更新 |
| DELETE | /api/v1/notebooks/{id} | 删除 |
| POST | /api/v1/notebooks/{id}/documents/upload | 上传文档 |
| GET | /api/v1/notebooks/{id}/documents | 获取文档列表 |
| DELETE | /api/v1/notebooks/{id}/documents/{doc_id} | 删除专属文档 |
| POST | /api/v1/notebooks/{id}/references | 引用 Library 文档 |
| DELETE | /api/v1/notebooks/{id}/references/{ref_id} | 取消引用 |

### 12.3 Session 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/notebooks/{id}/sessions | 创建 Session |
| GET | /api/v1/notebooks/{id}/sessions | 获取列表 |
| GET | /api/v1/notebooks/{id}/sessions/latest | 获取最近 Session |
| GET | /api/v1/sessions/{id} | 获取详情 |
| GET | /api/v1/sessions/{id}/messages | 获取消息历史 |
| GET | /api/v1/sessions/{id}/references | 获取引用列表 |
| DELETE | /api/v1/sessions/{id} | 删除 Session |

### 12.4 对话

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/notebooks/{id}/chat | 发送消息（非流式）|
| POST | /api/v1/notebooks/{id}/chat/stream | 发送消息（流式）|
| POST | /api/v1/notebooks/{id}/search | 在 Notebook 范围搜索 |
| POST | /api/v1/chat/stream/{msg_id}/cancel | 中断流式输出 |

### 12.5 文档内容

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/documents/{id} | 获取文档信息 |
| GET | /api/v1/documents/{id}/status | 获取处理状态 |
| GET | /api/v1/documents/{id}/content | 获取结构化内容 |
| GET | /api/v1/documents/{id}/chunks | 获取分块列表 |

### 12.6 引用管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/references | 创建引用 |
| GET | /api/v1/references/{id} | 获取详情 |
| DELETE | /api/v1/references/{id} | 删除引用 |

### 12.7 系统和健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/health | 基础健康检查 |
| GET | /api/v1/health/ready | 依赖就绪检查 |
| GET | /api/v1/health/live | 服务存活检查 |
| GET | /api/v1/info | 系统信息 |

---

## 13. 健康检查接口

### 13.1 基础健康检查

**请求**
```
GET /api/v1/health
```

**响应**
```json
{
    "status": "ok"
}
```

### 13.2 依赖就绪检查

**请求**
```
GET /api/v1/health/ready
```

**响应（成功）**
```json
{
    "status": "ready",
    "checks": {
        "postgresql": "ok",
        "redis": "ok",
        "elasticsearch": "ok"
    }
}
```

**响应（部分失败）**
```json
{
    "status": "not_ready",
    "checks": {
        "postgresql": "ok",
        "redis": "error: Connection refused",
        "elasticsearch": "ok"
    }
}
```

### 13.3 服务存活检查

**请求**
```
GET /api/v1/health/live
```

**响应**
```json
{
    "status": "alive"
}
```

---

最后更新：2026-01-19
版本：v1.0.1
