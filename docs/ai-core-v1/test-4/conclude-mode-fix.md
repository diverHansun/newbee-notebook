# Conclude模式外键约束错误修复方案

## 1. 问题描述

### 1.1 错误信息

```
sqlalchemy.exc.IntegrityError: insert or update on table "references"
violates foreign key constraint "references_document_id_fkey"
DETAIL: Key (document_id)=(d15a9d6d-3396-432f-874e-c10112fbd5c4) is not present in table "documents".
```

### 1.2 错误触发场景

- 调用Conclude模式的非流式或流式接口
- 系统成功检索RAG内容并生成响应
- 在保存reference记录时失败

---

## 2. 根因分析

### 2.1 数据不一致现象

通过数据库查询发现，`documents`表与`pgvector`表中的`document_id`完全不匹配：

| 文件名 | documents表ID | pgvector表document_id |
|--------|---------------|----------------------|
| test_document.txt | 6b62bf9e-a682-4fe2-94bb-82679655ef46 | 9d277931-c0b3-4e64-a37c-796c1c4cb76f |
| test_document2.txt | 7d2e5238-74cc-40bf-b123-6e9728408d38 | c3f1bbaf-f2d5-4aed-a331-720176364c6c |
| test_document3.txt | 7c47ead8-3d81-4119-be0e-4b2b439c476a | 1530a175-5110-4b4f-a0f3-88e1e13b9c7b |
| diabetes_guide.txt | 不存在 | fbc9c23d-4668-4154-af6a-80e6e4eb6335 |

### 2.2 LlamaIndex metadata覆盖问题

深入分析pgvector表的`metadata_`字段结构：

```json
{
  "ref_doc_id": "fbc9c23d-...",           // 被覆盖的错误值
  "doc_id": "fbc9c23d-...",               // 被覆盖的错误值
  "document_id": "fbc9c23d-...",          // 被覆盖的错误值
  "_node_content": {
    "metadata": {
      "ref_doc_id": "d15a9d6d-...",       // 原始正确值
      "doc_id": "d15a9d6d-...",           // 原始正确值
      "document_id": "d15a9d6d-..."       // 原始正确值
    },
    "relationships": {
      "1": {
        "node_id": "fbc9c23d-..."         // parent node的内部ID
      }
    }
  }
}
```

**关键发现**：
1. 顶层`metadata_`中的`document_id`被LlamaIndex覆盖为parent node的内部ID
2. 原始正确的`document_id`保存在`_node_content.metadata`中
3. `filters.py`注释已说明此问题，但sources提取逻辑未做相应处理

### 2.3 问题代码位置

`document_tasks.py`中正确设置了metadata：

```python
# 第67-78行: 创建LlamaDocument时设置metadata
llama_doc = LlamaDocument(
    text=text,
    metadata={
        "ref_doc_id": document.document_id,
        "doc_id": document.document_id,
        "document_id": document.document_id,  # 正确设置
        ...
    },
)

# 第88-90行: 节点处理时再次设置
meta["ref_doc_id"] = document.document_id
meta["doc_id"] = document.document_id
meta["document_id"] = document.document_id
```

但在`VectorStoreIndex.insert_nodes()`调用时，LlamaIndex内部会：
1. 为每个node生成新的`node_id`
2. 建立parent-child关系
3. 用parent node的`node_id`覆盖子节点的`ref_doc_id`

### 2.4 Sources提取逻辑缺陷

所有模式的sources提取都使用顶层metadata（被覆盖的错误值）：

```python
# conclude_mode.py 第146-149行
meta = getattr(n.node, "metadata", {})
sources.append({
    "document_id": meta.get("document_id"),  # 获取到被覆盖的错误ID
    ...
})
```

相同问题存在于：
- `explain_mode.py` 第152-155行
- `ask_mode.py` 第212-215行
- `chat_mode.py` 第221-222行

---

## 3. 解决方案

### 3.1 方案概述

创建统一的document_id提取函数，优先从`_node_content.metadata`获取正确值。

### 3.2 新增Helper函数

在`medimind_agent/core/engine/modes/base.py`或新建`utils.py`中添加：

```python
import json
from typing import Optional, Any

def extract_document_id(node: Any) -> Optional[str]:
    """从node中提取正确的document_id。

    LlamaIndex在insert_nodes时会用internal parent node ID覆盖
    顶层metadata的ref_doc_id/document_id。正确值保存在
    _node_content.metadata中。

    Args:
        node: LlamaIndex的NodeWithScore或BaseNode

    Returns:
        正确的document_id，如果无法提取则返回None
    """
    if not hasattr(node, "node"):
        node_obj = node
    else:
        node_obj = node.node

    metadata = getattr(node_obj, "metadata", {}) or {}

    # 优先从_node_content.metadata提取（原始正确值）
    node_content = metadata.get("_node_content")
    if node_content:
        if isinstance(node_content, str):
            try:
                node_content = json.loads(node_content)
            except json.JSONDecodeError:
                node_content = None

        if isinstance(node_content, dict):
            inner_meta = node_content.get("metadata", {})
            doc_id = inner_meta.get("document_id")
            if doc_id:
                return doc_id

    # Fallback: 使用顶层metadata（可能是错误值）
    return metadata.get("document_id")
```

### 3.3 修改各Mode的sources提取

#### 3.3.1 conclude_mode.py

```python
# 第143-153行修改为
from medimind_agent.core.engine.modes.utils import extract_document_id

source_nodes = getattr(response, "source_nodes", None)
if source_nodes:
    for n in source_nodes:
        sources.append({
            "document_id": extract_document_id(n),
            "chunk_id": getattr(n.node, "node_id", ""),
            "text": n.node.get_content(),
            "score": getattr(n, "score", 0.0),
        })
```

#### 3.3.2 explain_mode.py

同样修改第148-159行。

#### 3.3.3 ask_mode.py

修改第211-219行。

#### 3.3.4 chat_mode.py

修改第220-226行。

### 3.4 清理孤立数据

修复代码后，需要清理pgvector中的孤立数据：

```sql
-- 删除diabetes_guide.txt等不在documents表中的chunks
DELETE FROM data_documents_biobert
WHERE metadata_->>'title' NOT IN (
    SELECT title FROM documents
);
```

或者通过Admin API重新处理所有文档：

```bash
# 1. 清空pgvector表
# 2. 触发reprocess-pending重建索引
POST /api/v1/admin/reprocess-pending
{"dry_run": false}
```

### 3.5 可选：增加reference创建前验证

在`chat_service.py`的reference创建逻辑中增加验证：

```python
# 第143-156行修改
valid_refs = []
for src in sources:
    doc_id = src.get("document_id")
    if doc_id:
        # 验证document_id存在
        doc = await self._document_repo.get(doc_id)
        if doc:
            valid_refs.append(Reference(
                session_id=session_id,
                message_id=message_id,
                document_id=doc_id,
                chunk_id=src.get("chunk_id", ""),
                quoted_text=src.get("text", "")[:2000],
                context=None,
            ))
        else:
            logger.warning(f"Skipping reference for non-existent document: {doc_id}")

if valid_refs:
    await self._reference_repo.create_batch(valid_refs)
```

---

## 4. 实施步骤

1. **创建utils.py** - 添加`extract_document_id`函数
2. **修改四个mode文件** - 使用新函数提取document_id
3. **清理孤立数据** - 删除pgvector中的无效chunks
4. **重建索引** - 重新处理所有文档确保metadata正确
5. **验证修复** - 测试Conclude模式是否正常工作

---

## 5. 影响范围

| 文件 | 修改内容 |
|------|---------|
| `modes/utils.py` | 新建，添加extract_document_id函数 |
| `modes/conclude_mode.py` | 修改sources提取逻辑 |
| `modes/explain_mode.py` | 修改sources提取逻辑 |
| `modes/ask_mode.py` | 修改sources提取逻辑 |
| `modes/chat_mode.py` | 修改sources提取逻辑 |
| `chat_service.py` | 可选：增加document_id验证 |

---

## 6. 验证方法

```bash
# 1. 上传新文档
curl -X POST ".../documents/notebooks/{id}/upload" -F "file=@test.txt"

# 2. 等待处理完成后检查pgvector数据
SELECT metadata_->>'document_id' as pgvector_id,
       (metadata_->'_node_content'->'metadata'->>'document_id') as correct_id
FROM data_documents_biobert;

# 3. 测试Conclude模式
curl -X POST ".../chat/notebooks/{id}/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "summarize", "mode": "conclude", "session_id": "..."}'

# 4. 验证reference记录创建成功
SELECT * FROM references ORDER BY created_at DESC LIMIT 5;
```
