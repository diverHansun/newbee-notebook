# 元数据过滤器IN操作符修复

## 问题描述

当Notebook关联文档后,Explain/Conclude/Ask模式执行时报错:
```
Vector Store only supports exact match filters. Please use ExactMatchFilter or FilterOperator.EQ instead.
```

### 复现步骤

1. 创建Notebook
2. 上传文档到Library并等待处理完成
3. 将文档关联到Notebook
4. 在该Notebook中使用Explain模式

### 影响范围

- Explain模式
- Conclude模式
- Ask模式
- Chat模式不受影响(不使用文档过滤)

## 根因分析

### 当前代码

`explain_mode.py`:
```python
async def _refresh_engine(self) -> None:
    filters = None
    if self.allowed_doc_ids:
        filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="document_id",
                    value=self.allowed_doc_ids,  # List[str]
                    operator=FilterOperator.IN,   # 问题所在
                )
            ]
        )
    self._retriever = build_hybrid_retriever(
        pgvector_index=self._index,
        es_index=self._es_index,
        metadata_filters=filters,
    )
```

### 问题定位

1. `build_hybrid_retriever`将`filters`传递给pgvector和ES两个检索器
2. pgvector存储支持IN操作符(见`postgres/base.py:666`)
3. ES存储使用`legacy_filters()`方法转换过滤器
4. `legacy_filters()`仅支持EQ操作符:

`llama_index/core/vector_stores/types.py`:
```python
def legacy_filters(self) -> List[ExactMatchFilter]:
    filters = []
    for filter in self.filters:
        if filter.operator != FilterOperator.EQ:
            raise ValueError(
                "Vector Store only supports exact match filters. "
                "Please use ExactMatchFilter or FilterOperator.EQ instead."
            )
        filters.append(ExactMatchFilter(key=filter.key, value=filter.value))
    return filters
```

### 调用链

```
explain_mode._refresh_engine()
  └─ build_hybrid_retriever(metadata_filters=filters)
       ├─ pgvector_index.as_retriever(filters=metadata_filters)
       │    └─ PGVectorStore._build_filter_clause()  # 支持IN
       └─ es_index.as_retriever(filters=metadata_filters)
            └─ ElasticsearchStore.query()
                 └─ standard_filters.legacy_filters()  # 仅支持EQ,抛出异常
```

## 解决方案

### 方案A: 将IN操作拆分为多个EQ的OR组合 (推荐)

对于ES检索器,将单个IN过滤器拆分为多个EQ过滤器:

```python
def _build_document_filters(doc_ids: List[str]) -> MetadataFilters:
    """Build metadata filters for document IDs.

    For single document: use EQ operator
    For multiple documents: use multiple EQ filters with OR condition
    """
    if len(doc_ids) == 1:
        return MetadataFilters(
            filters=[
                MetadataFilter(
                    key="doc_id",
                    value=doc_ids[0],
                    operator=FilterOperator.EQ,
                )
            ]
        )

    # Multiple documents: OR of EQ filters
    return MetadataFilters(
        filters=[
            MetadataFilter(
                key="doc_id",
                value=doc_id,
                operator=FilterOperator.EQ,
            )
            for doc_id in doc_ids
        ],
        condition="or",  # MetadataFilters支持condition参数
    )
```

**优点**:
- 兼容ES存储的legacy_filters限制
- 无需修改LlamaIndex源码

**缺点**:
- 文档数量多时过滤器数量增加

### 方案B: 分别构建pgvector和ES的过滤器

为两个检索器使用不同的过滤器:

```python
def build_hybrid_retriever(
    pgvector_index,
    es_index,
    doc_ids: Optional[List[str]] = None,
    ...
) -> HybridRetriever:
    pgvector_filters = None
    es_filters = None

    if doc_ids:
        # pgvector支持IN
        pgvector_filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="doc_id",
                    value=doc_ids,
                    operator=FilterOperator.IN,
                )
            ]
        )

        # ES只支持EQ,使用OR组合
        es_filters = MetadataFilters(
            filters=[
                MetadataFilter(key="doc_id", value=doc_id, operator=FilterOperator.EQ)
                for doc_id in doc_ids
            ],
            condition="or",
        )

    pgvector_retriever = pgvector_index.as_retriever(filters=pgvector_filters)
    es_retriever = es_index.as_retriever(filters=es_filters)
    # ...
```

**优点**:
- 各存储使用最优的过滤方式
- pgvector利用IN的性能优势

**缺点**:
- 需要修改hybrid_retriever接口

### 方案C: 跳过ES过滤,在融合后过滤

ES检索不使用过滤器,在结果融合后按document_id过滤:

```python
class HybridRetriever(BaseRetriever):
    def __init__(self, ..., allowed_doc_ids: Optional[List[str]] = None):
        self._allowed_doc_ids = set(allowed_doc_ids) if allowed_doc_ids else None

    def _retrieve(self, query_bundle):
        pgvector_results = self._pgvector_retriever.retrieve(query_bundle)
        es_results = self._es_retriever.retrieve(query_bundle)

        fused = self._fusion_strategy.fuse([pgvector_results, es_results])

        # 后过滤
        if self._allowed_doc_ids:
            fused = [
                node for node in fused
                if node.metadata.get("doc_id") in self._allowed_doc_ids
            ]
        return fused[:self._top_k]
```

**优点**:
- 实现简单
- 不依赖存储层过滤能力

**缺点**:
- ES检索大量无关数据后丢弃,效率低
- 可能导致最终结果数量不足

## 推荐方案

**采用方案A**: 将IN操作拆分为多个EQ的OR组合

理由:
1. 兼容性最好,无需修改LlamaIndex
2. 对于典型场景(Notebook关联10-50个文档),过滤器数量可接受
3. MetadataFilters原生支持condition="or"

## 代码修改

### 新增辅助函数

`medimind_agent/core/rag/retrieval/filters.py`:
```python
"""Metadata filter utilities for vector store compatibility."""

from typing import List, Optional
from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator


def build_document_filter(doc_ids: Optional[List[str]]) -> Optional[MetadataFilters]:
    """Build compatible metadata filters for document IDs.

    Uses EQ operator with OR condition for ES compatibility.

    Args:
        doc_ids: List of document IDs to filter

    Returns:
        MetadataFilters or None if no doc_ids
    """
    if not doc_ids:
        return None

    if len(doc_ids) == 1:
        return MetadataFilters(
            filters=[
                MetadataFilter(
                    key="doc_id",
                    value=doc_ids[0],
                    operator=FilterOperator.EQ,
                )
            ]
        )

    return MetadataFilters(
        filters=[
            MetadataFilter(
                key="doc_id",
                value=doc_id,
                operator=FilterOperator.EQ,
            )
            for doc_id in doc_ids
        ],
        condition="or",
    )
```

### 修改模式文件

`explain_mode.py`, `conclude_mode.py`, `ask_mode.py`:

```python
from medimind_agent.core.rag.retrieval.filters import build_document_filter

async def _refresh_engine(self) -> None:
    filters = build_document_filter(self.allowed_doc_ids)

    self._retriever = build_hybrid_retriever(
        pgvector_index=self._index,
        es_index=self._es_index,
        metadata_filters=filters,
        # ...
    )
```

### 修改chat_mode.py

```python
from medimind_agent.core.rag.retrieval.filters import build_document_filter

# 在_build_search_tool方法中
filters = build_document_filter(self.allowed_doc_ids)
```

## 元数据键名一致性

注意检查存储时的元数据键名:

- 文档处理时设置: `node.metadata["doc_id"] = document_id`
- 过滤时查询: `key="doc_id"`

确保两者一致。如果当前使用`document_id`,需统一修改。

## 验证步骤

1. 创建Notebook并关联文档:
```bash
# 创建notebook
NB_ID=$(curl -s -X POST http://localhost:8000/api/v1/notebooks \
  -H "Content-Type: application/json" \
  -d '{"title":"Filter Test"}' | jq -r '.notebook_id')

# 上传文档
DOC_ID=$(curl -s -X POST http://localhost:8000/api/v1/documents/library/upload \
  -F "file=@test.txt" | jq -r '.document_id')

# 等待处理
sleep 20

# 关联
curl -X POST "http://localhost:8000/api/v1/notebooks/$NB_ID/references" \
  -H "Content-Type: application/json" \
  -d "{\"document_id\":\"$DOC_ID\"}"
```

2. 测试Explain模式:
```bash
curl -X POST "http://localhost:8000/api/v1/chat/notebooks/$NB_ID/chat" \
  -H "Content-Type: application/json" \
  -d '{"message":"What is this about?","mode":"explain"}'
```

3. 验证返回200且包含sources
