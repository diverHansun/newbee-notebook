# 数据流与 API 接口定义

## 1. 上下文与范围

本文档描述归档导出的后端数据流：从 API 层接收请求，到 ExportService 编排 Service 调用，到 manifest 构建、ZIP 打包并响应。

本模块与以下已有模块交互：

| 模块 | 交互方式 | 说明 |
|------|------|------|
| NotebookService | 方法调用 | 校验 Notebook 是否存在，获取 Notebook 元信息（标题、描述） |
| NotebookDocumentService | 方法调用 | 获取 Notebook 关联的文档列表 |
| DocumentService | 方法调用 | 获取文档 Markdown 内容和元数据（content_type、page_count 等） |
| NoteService | 方法调用 | 获取 Notebook 关联的笔记列表和内容 |
| MarkService | 方法调用 | 获取 Notebook 关联的书签列表 |
| DiagramService | 方法调用 | 获取图表列表和源码内容 |
| VideoService | 方法调用 | 获取视频总结列表和内容 |

## 2. 数据流描述

### 2.1 完整请求处理流

```
前端
  │
│  GET /api/v1/notebooks/{notebook_id}/export?types=documents,notes
  ▼
API 层 (routers/export.py)
  │
  ├─ 1. 解析路径参数 notebook_id
  ├─ 2. 解析查询参数 types（逗号分隔 → Set）
  ├─ 3. 校验 notebook 是否存在（调用 NotebookService）
  │     └─ 不存在 → 404
  ├─ 4. 调用 ExportService.export_notebook(notebook_id, types)
  │
  ▼
ExportService (services/export_service.py)
  │
  ├─ 5. 获取 Notebook 元信息（title, description）
  ├─ 6. 初始化 manifest 数据结构
  ├─ 7. 创建 BytesIO + ZipFile
  ├─ 8. 根据 types 分支执行：
  │     │
  │     ├─ "documents" in types:
  │     │   ├─ NotebookDocumentService.list_documents(notebook_id, limit, offset) 分页拉取
  │     │   └─ 对每个 doc:
  │     │       ├─ DocumentService.get_document_content(doc_id)
  │     │       ├─ 写入 ZIP: documents/{safe_title}_{doc_id}.md
  │     │       └─ 追加到 manifest.documents（含 document_id, title, content_type, page_count, chunk_count, file）
  │     │
  │     ├─ "notes" in types:
  │     │   ├─ NoteService.list_by_notebook(notebook_id)
  │     │   └─ 对每个 note:
  │     │       ├─ 写入 ZIP: notes/{safe_title}_{note_id}.md
  │     │       └─ 追加到 manifest.notes（含 note_id, title, file, document_ids, mark_ids）
  │     │
  │     ├─ "marks" in types:
  │     │   ├─ MarkService.list_by_notebook(notebook_id)
  │     │   ├─ 序列化为 JSON 数组
  │     │   ├─ 写入 ZIP: marks/marks.json
  │     │   └─ 写入 manifest.marks（含 file, count）
  │     │
  │     ├─ "diagrams" in types:
  │     │   ├─ DiagramService.list_diagrams(notebook_id)
  │     │   └─ 对每个 diagram:
  │     │       ├─ DiagramService.get_diagram_content(diagram_id, notebook_id)
  │     │       ├─ 写入 ZIP: diagrams/{safe_title}_{diagram_id}.{ext}
  │     │       └─ 追加到 manifest.diagrams（含 diagram_id, title, diagram_type, format, file, document_ids）
  │     │
  │     └─ "video_summaries" in types:
  │         ├─ 列出 Notebook 关联的视频总结
  │         └─ 对每个 summary:
  │             ├─ 写入 ZIP: video-summaries/{safe_title}_{summary_id}.md
  │             └─ 追加到 manifest.video_summaries（含 summary_id, title, platform, video_id, file）
  │
  ├─ 9. 将 manifest 序列化为 JSON，写入 ZIP: manifest.json
  ├─ 10. 如有失败条目，写入 ZIP: export-errors.txt
  ├─ 11. 关闭 ZipFile
  └─ 12. 返回 (BytesIO, suggested_filename)
  │
  ▼
API 层
  │
  ├─ 13. 从 BytesIO 构造 StreamingResponse
  ├─ 14. 设置 Content-Type: application/zip
  ├─ 15. 设置 Content-Disposition: attachment; filename="..."
  └─ 16. 返回响应
```

### 2.2 单条内容获取失败的处理

在步骤 8 中，如果单条 document/diagram/video-summary 的内容获取失败（如文档尚未解析完成、存储后端暂时不可用），采取以下策略：

- 跳过该条目，不写入 ZIP 对应文件，不追加到 manifest 对应列表
- 收集失败信息（条目 ID、类型、错误原因）
- 在步骤 10 中将所有失败信息写入 `export-errors.txt`
- 不中断整体导出流程
- 不返回 HTTP 错误码（只要 ZIP 构造本身成功）

## 3. API 接口定义

### 3.1 导出端点

```
GET /api/v1/notebooks/{notebook_id}/export
```

路径参数：

| 参数 | 类型 | 说明 |
|------|------|------|
| notebook_id | string (UUID) | Notebook ID |

查询参数：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|------|------|
| types | string | 否 | 全部类型 | 逗号分隔的内容类型列表 |

types 的合法值：

| 值 | 说明 |
|------|------|
| documents | 解析后的文档 Markdown |
| notes | 笔记 |
| marks | 书签 |
| diagrams | 图表源码 |
| video_summaries | 视频总结 |

成功响应：

| 项 | 值 |
|------|------|
| 状态码 | 200 |
| Content-Type | application/zip |
| Content-Disposition | attachment; filename="{notebook_title}-export-{YYYY-MM-DD}.zip" |
| Body | ZIP 二进制流 |

错误响应：

| 状态码 | 条件 | Body |
|------|------|------|
| 404 | Notebook 不存在 | `{"detail": "Notebook not found"}` |
| 422 | types 参数包含非法值 | `{"detail": "Invalid export type: xxx"}` |

### 3.2 请求模型

```python
VALID_EXPORT_TYPES = {"documents", "notes", "marks", "diagrams", "video_summaries"}
```

不需要 Pydantic 请求模型，参数通过 Path 和 Query 注入。

### 3.3 路由实现概述

```python
@router.get("/notebooks/{notebook_id}/export")
async def export_notebook(
    notebook_id: str = Path(...),
    types: Optional[str] = Query(None),
    notebook_service: NotebookService = Depends(get_notebook_service),
    export_service: ExportService = Depends(get_export_service),
) -> StreamingResponse:
    # 1. 校验 Notebook 存在
    notebook = await notebook_service.get_or_raise(notebook_id)
    # 2. 解析并校验 types
    requested_types = parse_export_types(types)
    # 3. 调用 export_service
    zip_buffer, filename = await export_service.export_notebook(notebook_id, requested_types)
    # 4. 构造 StreamingResponse
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

## 4. ExportService 接口

```python
class ExportService:
    async def export_notebook(
        self,
        notebook_id: str,
        types: set[str],
    ) -> tuple[io.BytesIO, str]:
        """
        返回 (zip_buffer, suggested_filename)

        zip_buffer: 包含 ZIP 内容的 BytesIO，已 seek 到起始位置
        suggested_filename: 格式为 {safe_notebook_title}-export-{YYYY-MM-DD}.zip
        """
```

## 5. 依赖注入

ExportService 的构造依赖：

```python
class ExportService:
    def __init__(
        self,
        notebook_service: NotebookService,
        notebook_document_service: NotebookDocumentService,
        document_service: DocumentService,
        note_service: NoteService,
        mark_service: MarkService,
        diagram_service: DiagramService,
        video_service: VideoService,
    ):
```

在 DI 容器中注册时，所有依赖均为已有的 Service 实例。
