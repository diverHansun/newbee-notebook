# Context增强方案: selected_text

## 1. 概述

本文档描述如何改进Explain和Conclude模式,使其能够有效利用前端传递的selected_text参数。

---

## 2. 问题分析

### 2.1 当前实现

前端发送的请求:

```json
{
  "message": "请解释这段内容",
  "mode": "explain",
  "context": {
    "document_id": "xxx",
    "selected_text": "机器学习是人工智能的一个子集..."
  }
}
```

后端Explain/Conclude模式的_process方法:

```python
async def _process(self, message: str) -> str:
    response = await self._query_engine.aquery(message)  # 直接使用message
    return str(response)
```

问题: selected_text被存储在self._context中,但未被使用。

### 2.2 期望行为

1. 用户在文档阅读器中选中一段文字
2. 点击Explain或Conclude按钮
3. 后端基于选中的文字进行分析
4. 返回与选中内容相关的解释或总结

---

## 3. 解决方案

### 3.1 修改explain_mode.py

```python
# core/engine/modes/explain_mode.py

async def _process(self, message: str) -> str:
    """Process explanation request using QueryEngine."""
    if self.scope_changed():
        await self._refresh_engine()

    # 构建增强查询
    query = self._build_enhanced_query(message)

    try:
        response = await self._query_engine.aquery(query)
    except AttributeError:
        response = self._query_engine.query(query)

    # 收集sources
    sources = []
    source_nodes = getattr(response, "source_nodes", None)
    if source_nodes:
        for n in source_nodes:
            meta = getattr(n.node, "metadata", {})
            sources.append({
                "document_id": meta.get("document_id"),
                "chunk_id": getattr(n.node, "node_id", ""),
                "text": n.node.get_content(),
                "score": getattr(n, "score", 0.0),
            })
    self._last_sources = sources
    return str(response)


def _build_enhanced_query(self, message: str) -> str:
    """根据context构建增强查询"""
    if not self._context:
        return message

    selected_text = self._context.get("selected_text")
    if not selected_text:
        return message

    # Explain模式: 精确匹配+语义理解
    return f"""请对以下选中的文本内容进行详细解释:

选中内容:
---
{selected_text}
---

用户问题: {message}

要求:
1. 首先解释选中文本的核心概念
2. 结合知识库中的相关信息补充说明
3. 如有专业术语,给出通俗解释
4. 保持回答简洁清晰"""
```

### 3.2 修改conclude_mode.py

```python
# core/engine/modes/conclude_mode.py

async def _process(self, message: str) -> str:
    """Process summarization request using ChatEngine."""
    current_scope = tuple(sorted(self.allowed_doc_ids)) if self.allowed_doc_ids else None
    if current_scope != self._filters_cache:
        await self._refresh_engine()
        self._filters_cache = current_scope
    if self.scope_changed():
        await self._refresh_engine()

    # 构建增强查询
    query = self._build_enhanced_query(message)

    try:
        response = await self._chat_engine.aquery(query)
    except AttributeError:
        response = self._chat_engine.query(query)

    # 收集sources
    sources = []
    source_nodes = getattr(response, "source_nodes", None)
    if source_nodes:
        for n in source_nodes:
            meta = getattr(n.node, "metadata", {})
            sources.append({
                "document_id": meta.get("document_id"),
                "chunk_id": getattr(n.node, "node_id", ""),
                "text": n.node.get_content(),
                "score": getattr(n, "score", 0.0),
            })
    self._last_sources = sources
    return str(response)


def _build_enhanced_query(self, message: str) -> str:
    """根据context构建增强查询"""
    if not self._context:
        return message

    selected_text = self._context.get("selected_text")
    if not selected_text:
        return message

    # Conclude模式: 总结选中内容
    return f"""请对以下选中的文本内容进行总结:

选中内容:
---
{selected_text}
---

用户要求: {message}

要求:
1. 提取选中内容的核心观点
2. 按逻辑顺序组织总结
3. 如内容较长,分点列出关键信息
4. 结合知识库信息补充上下文"""
```

### 3.3 基类扩展

在BaseMode中添加通用方法:

```python
# core/engine/modes/base.py

class BaseMode(ABC):
    # ... 现有代码 ...

    def get_selected_text(self) -> Optional[str]:
        """获取context中的selected_text"""
        if self._context:
            return self._context.get("selected_text")
        return None

    def get_context_document_id(self) -> Optional[str]:
        """获取context中的document_id"""
        if self._context:
            return self._context.get("document_id")
        return None
```

---

## 4. Explain vs Conclude的区别处理

### 4.1 Explain模式特点

- 目的: 解释概念、术语、原理
- 选中内容: 通常是短语、句子或段落
- 检索策略: ES精确匹配 + pgvector语义检索
- 响应风格: 教学式,由浅入深

### 4.2 Conclude模式特点

- 目的: 总结、归纳、提炼要点
- 选中内容: 通常是段落、章节或多段文字
- 检索策略: pgvector语义检索(获取相关上下文)
- 响应风格: 概括式,分点列出

### 4.3 后续改进: Explain模式集成ES

```python
# 后续实现: explain_mode.py

async def _refresh_engine(self) -> None:
    """使用HybridRetriever重建检索引擎"""
    filters = None
    if self.allowed_doc_ids:
        filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="document_id",
                    value=self.allowed_doc_ids,
                    operator=FilterOperator.IN,
                )
            ]
        )

    # 构建混合检索器: pgvector + ES
    from medimind_agent.core.rag.retrieval import build_hybrid_retriever

    self._hybrid_retriever = build_hybrid_retriever(
        pgvector_index=self._pgvector_index,
        es_index=self._es_index,
        pgvector_top_k=self._pgvector_top_k,
        es_top_k=self._es_top_k,
        final_top_k=self._final_top_k,
        metadata_filters=filters,
    )

    self._query_engine = RetrieverQueryEngine.from_args(
        retriever=self._hybrid_retriever,
        llm=self._llm,
        response_mode=self._response_mode,
        text_qa_template=EXPLAIN_QA_TEMPLATE,
        verbose=self._config.verbose,
    )
```

---

## 5. 测试用例

### 5.1 Explain模式测试

```bash
curl -X POST "http://localhost:8000/api/v1/chat/notebooks/{notebook_id}/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "请详细解释",
    "mode": "explain",
    "session_id": "{session_id}",
    "context": {
      "document_id": "{doc_id}",
      "selected_text": "机器学习是人工智能的一个子集,它使计算机能够从数据中学习而无需明确编程"
    }
  }'
```

期望结果:
- 响应内容针对"机器学习"概念进行解释
- sources中包含与选中文字相关的文档片段

### 5.2 Conclude模式测试

```bash
curl -X POST "http://localhost:8000/api/v1/chat/notebooks/{notebook_id}/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "请总结这段内容的要点",
    "mode": "conclude",
    "session_id": "{session_id}",
    "context": {
      "document_id": "{doc_id}",
      "selected_text": "深度学习是机器学习的一个分支...（较长的段落）..."
    }
  }'
```

期望结果:
- 响应内容是对选中段落的总结
- 分点列出关键信息
- sources中包含相关上下文

---

## 6. 注意事项

1. selected_text长度限制: 过长的文本需要截断或分段处理
2. 空白处理: 去除selected_text首尾空白
3. 编码问题: 确保中文内容正确处理
4. 性能考虑: 增强查询会增加token消耗,注意监控

---

## 7. 实施步骤

1. 修改explain_mode.py,添加_build_enhanced_query方法
2. 修改conclude_mode.py,添加_build_enhanced_query方法
3. 在base.py中添加辅助方法
4. 编写单元测试
5. 进行集成测试
6. 更新API文档
