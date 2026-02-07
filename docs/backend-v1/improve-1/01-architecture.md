# 架构设计

## 1. 存储结构

### 1.1 当前结构（存在问题）

```
data/documents/
├── pdf/                          # 原始 PDF 文件
│   └── {原始文件名}.pdf
├── word/                         # 原始 Word 文件
│   └── {原始文件名}.docx
├── excel/, csv/, md/, txt/       # 其他类型原始文件
│
└── {document_id}/                # 转换后的文件
    ├── content.md
    └── images/
```

**问题**：
- 原始文件按类型分类存储，与 `document_id` 无直接关联
- 无法通过 `document_id` 直接定位原始文件
- 删除时需要分别清理两个位置

### 1.2 新存储结构

```
data/documents/
└── {document_id}/
    ├── original/
    │   └── {原始文件名}.ext      # 保留原始文件名，便于下载
    ├── markdown/
    │   └── content.md            # 转换后的 Markdown
    └── images/                   # 提取的图片
        └── 000.bin, 001.bin...
```

**优点**：
- 通过 `document_id` 可直接定位所有相关文件
- 删除时只需删除整个目录
- 原始文件名保留，下载时有意义
- 结构清晰，便于维护

### 1.3 路径映射

| 字段 | 存储路径 |
|------|----------|
| `Document.file_path` | `{document_id}/original/{原始文件名}` |
| `Document.content_path` | `{document_id}/markdown/content.md` |

## 2. 处理流程

### 2.1 文档生命周期

```
┌─────────────────────────────────────────────────────────────────────┐
│                    阶段一：上传到 Library                            │
├─────────────────────────────────────────────────────────────────────┤
│  输入：用户上传的文件（PDF, Word, Excel 等）                         │
│                                                                     │
│  处理：                                                             │
│    1. 生成 document_id (UUID)                                       │
│    2. 创建目录 {document_id}/original/                              │
│    3. 保存原始文件（保留原文件名）                                   │
│    4. 创建 Document 记录                                            │
│                                                                     │
│  输出：status = UPLOADED                                            │
│                                                                     │
│  注意：此阶段不进行转换，不进行 Embedding                            │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    阶段二：添加到 Notebook                           │
├─────────────────────────────────────────────────────────────────────┤
│  输入：document_id 列表 + notebook_id                                │
│                                                                     │
│  处理：                                                             │
│    1. 创建 NotebookDocumentRef 记录                                 │
│    2. 为每个文档创建 Celery 任务：                                   │
│       a. 文档转换（MinerU / MarkItDown）                            │
│       b. 保存 Markdown 到 {document_id}/markdown/                   │
│       c. 文本分块（Chunking）                                       │
│       d. 向量化（Embedding）                                        │
│       e. 索引到 pgvector + Elasticsearch                            │
│    3. 更新 Document 状态和元数据                                     │
│                                                                     │
│  输出：status = PROCESSING -> COMPLETED                             │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      阶段三：问答使用                                │
├─────────────────────────────────────────────────────────────────────┤
│  输入：用户问题 + notebook_id                                        │
│                                                                     │
│  处理：                                                             │
│    1. 获取 Notebook 关联的所有 document_id                          │
│    2. RAG 检索时按 document_id 过滤                                 │
│    3. 生成答案                                                      │
│                                                                     │
│  输出：答案 + 来源引用                                               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      阶段四：文档管理                                │
├─────────────────────────────────────────────────────────────────────┤
│  操作 A：从 Notebook 移除（软移除）                                  │
│    - 删除 NotebookDocumentRef 记录                                  │
│    - 不删除向量、文件、Document 记录                                 │
│                                                                     │
│  操作 B：从 Library 删除（硬删除）                                   │
│    - 检查 Notebook 引用（可强制删除）                                │
│    - 删除所有 NotebookDocumentRef                                   │
│    - 删除 pgvector 向量                                             │
│    - 删除 Elasticsearch 索引                                        │
│    - 删除整个 {document_id}/ 目录                                   │
│    - 删除 Document 数据库记录                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 状态流转图

```
                    ┌──────────────────────────────┐
                    │           PENDING            │
                    │        （初始状态）           │
                    └──────────────┬───────────────┘
                                   │
                         上传文件保存成功
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │          UPLOADED            │
                    │    （已上传，等待处理）        │
                    └──────────────┬───────────────┘
                                   │
                      添加到 Notebook，触发处理
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │         PROCESSING           │
                    │   （转换 + Embedding 中）     │
                    └───────┬──────────────┬───────┘
                            │              │
                       处理成功         处理失败
                            │              │
                            ▼              ▼
          ┌─────────────────────┐   ┌─────────────────────┐
          │      COMPLETED      │   │       FAILED        │
          │    （处理完成）      │   │    （处理失败）      │
          └─────────────────────┘   └─────────────────────┘
```

### 2.3 重复添加处理

当同一文档被添加到多个 Notebook 时：

1. 第一次添加：触发完整处理（转换 + Embedding）
2. 后续添加：仅创建 NotebookDocumentRef，复用已有的向量数据

```python
def add_documents_to_notebook(notebook_id: str, document_ids: List[str]):
    for doc_id in document_ids:
        # 检查关联是否已存在
        if ref_exists(notebook_id, doc_id):
            continue  # 跳过已添加的
        
        # 创建关联
        create_ref(notebook_id, doc_id)
        
        # 检查是否需要处理
        doc = get_document(doc_id)
        if doc.status == DocumentStatus.UPLOADED:
            # 首次添加，触发处理
            process_document_task.delay(doc_id)
        # 如果 status 已是 COMPLETED，无需再次处理
```

## 3. Celery 任务设计

### 3.1 任务定义

```python
@celery_app.task(bind=True, max_retries=3)
def process_document_task(self, document_id: str):
    """
    处理文档：转换 + Embedding + 索引
    
    步骤：
    1. 更新状态为 PROCESSING
    2. 文档转换（MinerU / MarkItDown）
    3. 保存 Markdown 到 {document_id}/markdown/
    4. 文本分块
    5. Embedding
    6. 索引到 pgvector + Elasticsearch
    7. 更新状态为 COMPLETED
    
    失败时：
    - 更新状态为 FAILED
    - 记录错误信息
    - 根据配置决定是否重试
    """
    pass


@celery_app.task
def delete_document_data_task(document_id: str):
    """
    清理文档数据：向量 + 索引
    
    步骤：
    1. 删除 pgvector 向量
    2. 删除 Elasticsearch 索引
    
    注意：文件系统清理在主流程中同步执行
    """
    pass
```

### 3.2 任务队列配置

建议配置独立队列处理文档任务：

```python
CELERY_TASK_ROUTES = {
    'process_document_task': {'queue': 'document_processing'},
    'delete_document_data_task': {'queue': 'document_cleanup'},
}
```

## 4. 错误处理

### 4.1 上传阶段

| 错误类型 | 处理方式 |
|----------|----------|
| 文件类型不支持 | 返回 400 Bad Request |
| 文件过大 | 返回 413 Payload Too Large |
| 存储空间不足 | 返回 507 Insufficient Storage |

### 4.2 处理阶段

| 错误类型 | 处理方式 |
|----------|----------|
| 转换失败 | 标记 FAILED，记录错误信息，支持重试 |
| Embedding 失败 | 标记 FAILED，记录错误信息，支持重试 |
| 索引失败 | 标记 FAILED，记录错误信息，支持重试 |

### 4.3 删除阶段

| 错误类型 | 处理方式 |
|----------|----------|
| 有 Notebook 引用 | 返回 409 Conflict（除非 force=true） |
| 向量删除失败 | 记录警告，继续执行 |
| 文件删除失败 | 记录警告，继续执行 |

## 5. 并发控制

### 5.1 同一文档重复处理

使用数据库锁或 Redis 分布式锁防止重复处理：

```python
def process_document_task(document_id: str):
    lock_key = f"doc_processing:{document_id}"
    
    with redis_lock(lock_key, timeout=3600):
        doc = get_document(document_id)
        
        # 再次检查状态，防止重复处理
        if doc.status in [DocumentStatus.PROCESSING, DocumentStatus.COMPLETED]:
            return
        
        # 执行处理逻辑
        ...
```

### 5.2 批量添加

批量添加时，每个文档独立创建 Celery 任务，允许并行处理：

```python
def add_documents_to_notebook(notebook_id: str, document_ids: List[str]):
    tasks = []
    for doc_id in document_ids:
        # 创建关联
        create_ref(notebook_id, doc_id)
        
        # 创建任务（不等待）
        task = process_document_task.delay(doc_id)
        tasks.append(task)
    
    return tasks  # 返回任务 ID 列表，供前端轮询
```
