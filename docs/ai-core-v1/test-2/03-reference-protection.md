# 引用保护: 删除文档不丢失对话引用

## 问题描述

当前删除文档时，对话中的引用记录会被级联删除，导致历史对话丢失来源信息。

### 现状分析

**数据库约束** (`init-postgres.sql`):

```sql
CREATE TABLE references (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    message_id INTEGER NOT NULL,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id VARCHAR(100),
    quoted_text TEXT,
    ...
);
```

`document_id NOT NULL` + `ON DELETE CASCADE` 导致:
- 文档删除时，所有关联引用被自动删除
- 对话记录中的引用来源信息丢失

### 影响场景

1. 用户A上传文档X
2. 用户B在对话中引用文档X的内容，生成引用记录
3. 用户A删除文档X
4. 用户B的对话中引用信息消失，无法追溯来源

## 解决方案: 软保留引用

### 设计原则

- 对话记录是历史快照，应保持完整性
- 引用的`quoted_text`已保存文本内容，无需依赖原文档
- 删除文档后，引用应标记为"来源已删除"而非删除

### 数据库变更

**迁移脚本** `migrations/003_reference_soft_delete.sql`:

```sql
-- 1. 允许document_id为NULL
ALTER TABLE references ALTER COLUMN document_id DROP NOT NULL;

-- 2. 修改外键约束为SET NULL
ALTER TABLE references DROP CONSTRAINT references_document_id_fkey;
ALTER TABLE references ADD CONSTRAINT references_document_id_fkey
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL;

-- 3. 新增字段
ALTER TABLE references ADD COLUMN document_title VARCHAR(500);
ALTER TABLE references ADD COLUMN is_source_deleted BOOLEAN NOT NULL DEFAULT FALSE;
```

### 实体变更

**修改** `domain/entities/reference.py`:

```python
@dataclass
class Reference:
    session_id: str
    message_id: int
    document_id: Optional[str]  # 改为Optional
    chunk_id: str
    quoted_text: str
    document_title: Optional[str] = None  # 新增
    is_source_deleted: bool = False  # 新增
    context: Optional[str] = None
    id: Optional[int] = None
```

### 删除流程变更

**修改** `application/services/document_service.py` 的 `delete_document` 方法:

```python
async def delete_document(self, document_id: str, force: bool = False) -> bool:
    doc = await self._document_repo.get(document_id)
    if not doc:
        raise ValueError(f"Document not found: {document_id}")

    # 新增: 在删除前更新引用记录
    await self._reference_repo.mark_source_deleted(
        document_id=document_id,
        document_title=doc.title
    )

    # 原有逻辑...
    if doc.is_library_document:
        ref_count = await self._ref_repo.count_by_document(document_id)
        if ref_count > 0 and not force:
            raise RuntimeError(...)
        if ref_count > 0:
            await self._ref_repo.delete_by_document(document_id)

    # 删除文档记录
    result = await self._document_repo.delete(document_id)

    # 异步清理索引
    delete_document_nodes_task.delay(document_id)
    return result
```

### Repository新增方法

**新增** `domain/repositories/reference_repository.py`:

```python
class ReferenceRepository(ABC):
    @abstractmethod
    async def mark_source_deleted(
        self,
        document_id: str,
        document_title: str
    ) -> int:
        """标记文档关联的引用为已删除状态，返回影响行数"""
        pass
```

**实现** `infrastructure/persistence/repositories/reference_repo_impl.py`:

```python
async def mark_source_deleted(
    self,
    document_id: str,
    document_title: str
) -> int:
    result = await self._session.execute(
        update(ReferenceModel)
        .where(ReferenceModel.document_id == document_id)
        .values(
            document_title=document_title,
            is_source_deleted=True
        )
    )
    return result.rowcount
```

### 前端展示适配

API响应中引用数据结构:

```json
{
  "sources": [
    {
      "document_id": null,
      "document_title": "Clean Code.pdf",
      "chunk_id": "abc123",
      "quoted_text": "代码应该像散文一样易读...",
      "is_source_deleted": true
    }
  ]
}
```

前端处理逻辑:
- `is_source_deleted=true` 时显示"来源已删除"标记
- 使用`document_title`显示文档名称
- 禁用"跳转到原文"功能

## 数据一致性保证

### 删除流程顺序

```
1. mark_source_deleted()     # 标记引用
2. delete_by_document()      # 删除notebook_document_refs
3. delete()                  # 删除documents记录 (触发FK SET NULL)
4. delete_document_nodes_task()  # 异步清理索引
```

### 异常处理

若步骤1成功但后续失败:
- 引用已标记is_source_deleted=true
- 但document仍存在
- **影响**: 引用显示"已删除"但实际未删除
- **修复**: 管理接口批量修正或定时任务检查

建议将步骤1-3放入数据库事务中。

## 迁移策略

1. 执行数据库迁移脚本
2. 部署新版本代码
3. 无需历史数据迁移(现有引用document_id保持不变)
4. 新删除操作自动应用软保留逻辑
