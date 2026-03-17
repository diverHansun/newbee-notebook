# Note-Bookmark 模块：API 层设计

## 1. 定位

REST API 层为前端 Studio Panel 和 Markdown Viewer 提供数据接口。所有端点面向用户直接操作，不涉及 agent skill 激活逻辑（skill 层通过 Service 直接调用，不经过 REST API）。

## 2. Mark API

### 2.1 创建书签

```
POST /api/v1/documents/{document_id}/marks
```

请求体：

```json
{
    "anchor_text": "选中的文本内容",
    "char_offset": 12345,
    "comment": "可选短评"
}
```

响应（201）：

```json
{
    "mark_id": "uuid",
    "document_id": "uuid",
    "anchor_text": "选中的文本内容",
    "char_offset": 12345,
    "comment": "可选短评",
    "created_at": "2026-03-17T10:00:00Z",
    "updated_at": "2026-03-17T10:00:00Z"
}
```

校验规则：
- document_id 对应文档必须存在且状态为 converted 或 completed
- anchor_text 非空，最大 500 字符
- char_offset 非负整数

### 2.2 查询文档书签

```
GET /api/v1/documents/{document_id}/marks
```

响应（200）：

```json
{
    "marks": [
        {
            "mark_id": "uuid",
            "document_id": "uuid",
            "anchor_text": "...",
            "char_offset": 100,
            "comment": null,
            "created_at": "...",
            "updated_at": "..."
        }
    ],
    "total": 5
}
```

按 char_offset 升序排列。Viewer 渲染书签高亮时使用。

### 2.3 查询 Notebook 下所有书签

```
GET /api/v1/notebooks/{notebook_id}/marks
```

响应格式同上，按 created_at 降序排列。Studio 面板书签列表使用。

### 2.4 更新书签评论

```
PATCH /api/v1/marks/{mark_id}
```

请求体：

```json
{
    "comment": "更新后的短评"
}
```

响应（200）：完整 Mark 对象。

### 2.5 删除书签

```
DELETE /api/v1/marks/{mark_id}
```

响应（204）：无内容。

### 2.6 查询文档书签数量

```
GET /api/v1/documents/{document_id}/marks/count
```

响应（200）：

```json
{
    "count": 3
}
```

用途：前端删除文档前调用，获取 affected_marks_count 用于确认对话框提示。

## 3. Note API

### 3.1 创建笔记

```
POST /api/v1/notes
```

请求体：

```json
{
    "title": "笔记标题",
    "content": "",
    "document_ids": ["uuid1", "uuid2"]
}
```

document_ids 可选。如果提供，创建笔记的同时建立文档标签关联。

响应（201）：

```json
{
    "note_id": "uuid",
    "title": "笔记标题",
    "content": "",
    "document_ids": ["uuid1", "uuid2"],
    "created_at": "...",
    "updated_at": "..."
}
```

### 3.2 获取笔记

```
GET /api/v1/notes/{note_id}
```

响应（200）：

```json
{
    "note_id": "uuid",
    "title": "笔记标题",
    "content": "Markdown 内容...",
    "document_ids": ["uuid1", "uuid2"],
    "marks": [
        {
            "mark_id": "uuid",
            "document_id": "uuid",
            "anchor_text": "...",
            "char_offset": 100
        }
    ],
    "created_at": "...",
    "updated_at": "..."
}
```

响应中包含关联的 document_ids 和引用的 marks 列表，供前端编辑器渲染 wiki-link 预览。

### 3.3 更新笔记

```
PATCH /api/v1/notes/{note_id}
```

请求体（partial update）：

```json
{
    "title": "新标题",
    "content": "更新的 Markdown 内容..."
}
```

所有字段可选。auto-save 场景下通常只发送 content。

响应（200）：完整 Note 对象（同 3.2 格式）。

### 3.4 删除笔记

```
DELETE /api/v1/notes/{note_id}
```

响应（204）：无内容。

### 3.5 查询 Notebook 下的笔记

```
GET /api/v1/notebooks/{notebook_id}/notes?document_id=xxx
```

document_id 查询参数可选，用于按单文档过滤。

响应（200）：

```json
{
    "notes": [
        {
            "note_id": "uuid",
            "title": "...",
            "document_ids": ["uuid1"],
            "mark_count": 2,
            "created_at": "...",
            "updated_at": "..."
        }
    ],
    "total": 10
}
```

列表响应不包含 content 字段（避免大量数据传输），包含 mark_count 摘要。按 updated_at 降序。

## 4. Note-Document 关联 API

### 4.1 添加文档标签

```
POST /api/v1/notes/{note_id}/documents
```

请求体：

```json
{
    "document_id": "uuid"
}
```

响应（201）：

```json
{
    "note_id": "uuid",
    "document_id": "uuid",
    "created_at": "..."
}
```

幂等：重复添加返回 200 和已有记录。

### 4.2 移除文档标签

```
DELETE /api/v1/notes/{note_id}/documents/{document_id}
```

响应（204）：无内容。

### 4.3 获取笔记关联的文档

```
GET /api/v1/notes/{note_id}/documents
```

响应（200）：

```json
{
    "documents": [
        {
            "document_id": "uuid",
            "title": "文档标题"
        }
    ]
}
```

## 5. Note-Mark 引用 API

### 5.1 添加 Mark 引用

```
POST /api/v1/notes/{note_id}/marks
```

请求体：

```json
{
    "mark_id": "uuid"
}
```

响应（201）：引用记录。幂等。

### 5.2 移除 Mark 引用

```
DELETE /api/v1/notes/{note_id}/marks/{mark_id}
```

响应（204）：无内容。

### 5.3 获取笔记引用的 Marks

```
GET /api/v1/notes/{note_id}/marks
```

响应（200）：

```json
{
    "marks": [
        {
            "mark_id": "uuid",
            "document_id": "uuid",
            "anchor_text": "...",
            "char_offset": 100,
            "comment": null
        }
    ]
}
```

## 6. 现有 API 的增强

### 6.1 删除文档端点增强

现有 `DELETE /api/v1/documents/{document_id}` 和强制删除端点的响应中增加字段：

```json
{
    "deleted": true,
    "affected_marks_count": 3
}
```

实现方式：API 层在调用 DocumentService.delete_document 之前，先调用 MarkService.count_by_document 获取计数。不修改 DocumentService 内部逻辑。

## 7. 错误码

| 状态码 | 场景 |
|--------|------|
| 400 | anchor_text 为空、char_offset 为负 |
| 404 | mark_id / note_id / document_id 不存在 |
| 409 | 重复关联（由幂等处理覆盖，正常不应出现） |
| 422 | 文档状态不支持创建书签（未完成处理） |
