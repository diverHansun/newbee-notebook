# 数据模型变更

## 1. Document 实体

### 1.1 当前定义

```python
@dataclass
class Document(Entity):
    document_id: str
    title: str
    content_type: DocumentType
    file_path: str
    status: DocumentStatus
    library_id: Optional[str] = None
    notebook_id: Optional[str] = None  # 将废弃
    url: Optional[str] = None
    page_count: int = 0
    chunk_count: int = 0
    file_size: int = 0
    content_path: Optional[str] = None
    content_format: str = "markdown"
    content_size: int = 0
    error_message: Optional[str] = None
```

### 1.2 变更后定义

```python
@dataclass
class Document(Entity):
    document_id: str
    title: str                              # 原始文件名
    content_type: DocumentType
    file_path: str                          # {document_id}/original/{filename}
    status: DocumentStatus
    library_id: str                         # 必填，所有文档必须属于 Library
    url: Optional[str] = None               # 保留，用于 URL 导入场景
    page_count: int = 0
    chunk_count: int = 0
    file_size: int = 0
    content_path: Optional[str] = None      # {document_id}/markdown/content.md
    content_format: str = "markdown"
    content_size: int = 0
    error_message: Optional[str] = None
    
    # 废弃字段
    # notebook_id: Optional[str] = None     # 改用 NotebookDocumentRef
```

### 1.3 字段说明

| 字段 | 类型 | 描述 | 变更 |
|------|------|------|------|
| document_id | str | 文档唯一标识（UUID） | 无变更 |
| title | str | 原始文件名 | 无变更 |
| content_type | DocumentType | 文件类型 | 无变更 |
| file_path | str | 原始文件相对路径 | 格式变更 |
| status | DocumentStatus | 处理状态 | 状态值变更 |
| library_id | str | 所属 Library ID | 改为必填 |
| notebook_id | str | 所属 Notebook ID | 废弃 |
| content_path | str | Markdown 文件相对路径 | 格式变更 |

## 2. DocumentStatus 枚举

### 2.1 当前定义

```python
class DocumentStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
```

### 2.2 变更后定义

```python
class DocumentStatus(Enum):
    PENDING = "pending"         # 初始状态（创建记录但未保存文件）
    UPLOADED = "uploaded"       # 已上传，等待添加到 Notebook
    PROCESSING = "processing"   # 转换 + Embedding 处理中
    COMPLETED = "completed"     # 处理完成，可用于问答
    FAILED = "failed"           # 处理失败
```

### 2.3 状态说明

| 状态 | 触发条件 | 可执行操作 |
|------|----------|------------|
| PENDING | 创建 Document 记录 | 等待文件保存 |
| UPLOADED | 文件保存成功 | 添加到 Notebook、删除 |
| PROCESSING | 添加到 Notebook 后 | 等待处理完成 |
| COMPLETED | 处理成功 | 问答、预览、删除 |
| FAILED | 处理失败 | 重试、删除 |

## 3. NotebookDocumentRef 实体

### 3.1 定义

```python
@dataclass
class NotebookDocumentRef(Entity):
    """Notebook 与 Document 的关联记录"""
    id: str                     # 关联记录 ID（UUID）
    notebook_id: str            # Notebook ID（外键）
    document_id: str            # Document ID（外键）
    created_at: datetime        # 添加时间
```

### 3.2 数据库表结构

```sql
CREATE TABLE notebook_document_refs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uq_notebook_document UNIQUE (notebook_id, document_id)
);

CREATE INDEX idx_notebook_document_refs_notebook ON notebook_document_refs(notebook_id);
CREATE INDEX idx_notebook_document_refs_document ON notebook_document_refs(document_id);
```

### 3.3 业务规则

| 规则 | 描述 |
|------|------|
| 唯一性 | 同一 Notebook 不能重复添加同一 Document |
| 级联删除 | 删除 Notebook 时自动删除关联 |
| 级联删除 | 删除 Document 时自动删除关联 |
| 多对多 | 一个 Document 可被多个 Notebook 引用 |

## 4. 数据库迁移

### 4.1 迁移脚本

```sql
-- 1. 添加新状态值
ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'uploaded';

-- 2. 将现有 PENDING 状态更新为 UPLOADED（如果文件已存在）
UPDATE documents 
SET status = 'uploaded' 
WHERE status = 'pending' 
  AND file_path IS NOT NULL 
  AND file_path != '';

-- 3. 迁移 notebook_id 到 notebook_document_refs
INSERT INTO notebook_document_refs (notebook_id, document_id, created_at)
SELECT notebook_id, id, created_at
FROM documents
WHERE notebook_id IS NOT NULL
ON CONFLICT DO NOTHING;

-- 4. 清空 notebook_id 字段（可选，保持兼容性可暂不执行）
-- UPDATE documents SET notebook_id = NULL WHERE notebook_id IS NOT NULL;

-- 5. 确保所有文档都有 library_id
-- 如果存在没有 library_id 的文档，需要手动处理
SELECT id, title FROM documents WHERE library_id IS NULL;
```

### 4.2 Alembic 迁移

```python
"""Add uploaded status and migrate notebook documents

Revision ID: xxxx
"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    # 添加新状态
    op.execute("ALTER TYPE documentstatus ADD VALUE IF NOT EXISTS 'uploaded'")
    
    # 迁移 notebook_id 关联
    op.execute("""
        INSERT INTO notebook_document_refs (id, notebook_id, document_id, created_at)
        SELECT gen_random_uuid(), notebook_id, id, created_at
        FROM documents
        WHERE notebook_id IS NOT NULL
        ON CONFLICT (notebook_id, document_id) DO NOTHING
    """)

def downgrade():
    # 回滚迁移
    op.execute("""
        UPDATE documents d
        SET notebook_id = ndr.notebook_id
        FROM notebook_document_refs ndr
        WHERE d.id = ndr.document_id
    """)
```

## 5. 路径格式变更

### 5.1 file_path

| 项目 | 旧格式 | 新格式 |
|------|--------|--------|
| 示例 | `pdf/医学影像分析.pdf` | `{document_id}/original/医学影像分析.pdf` |
| 基础路径 | `data/documents/` | `data/documents/` |
| 完整路径 | `data/documents/pdf/医学影像分析.pdf` | `data/documents/{document_id}/original/医学影像分析.pdf` |

### 5.2 content_path

| 项目 | 旧格式 | 新格式 |
|------|--------|--------|
| 示例 | `{document_id}/content.md` | `{document_id}/markdown/content.md` |
| 基础路径 | `data/documents/` | `data/documents/` |
| 完整路径 | `data/documents/{document_id}/content.md` | `data/documents/{document_id}/markdown/content.md` |

## 6. 索引元数据

### 6.1 向量节点元数据

存储到 pgvector 和 Elasticsearch 的每个节点包含：

```python
{
    "ref_doc_id": "document_id",        # 用于按文档删除
    "doc_id": "document_id",            # 文档 ID
    "document_id": "document_id",       # 文档 ID（冗余，兼容）
    "library_id": "library_id",         # Library ID
    "chunk_index": 0,                   # 块索引
    "chunk_id": "node_id",              # 节点 ID
    "title": "文档标题",                 # 文档标题
    "content_type": "pdf"               # 文件类型
}
```

### 6.2 检索过滤

问答时按 Notebook 关联的文档过滤：

```python
# 获取 Notebook 关联的所有文档 ID
document_ids = [ref.document_id for ref in notebook_refs]

# 构建过滤条件
filters = MetadataFilters(
    filters=[
        MetadataFilter(
            key="document_id",
            value=document_ids,
            operator=FilterOperator.IN
        )
    ]
)

# 执行检索
results = retriever.retrieve(query, filters=filters)
```

## 7. 兼容性说明

### 7.1 向后兼容

| 项目 | 兼容策略 |
|------|----------|
| notebook_id 字段 | 暂时保留，新代码不使用 |
| 旧路径格式 | 代码同时支持新旧格式读取 |
| 废弃端点 | 返回 410 Gone 或 301 重定向 |

### 7.2 迁移步骤

1. 部署新代码（支持新旧格式）
2. 执行数据库迁移
3. 新文档使用新格式存储
4. 逐步清理旧格式文件（手动或脚本）
5. 移除旧格式支持代码
