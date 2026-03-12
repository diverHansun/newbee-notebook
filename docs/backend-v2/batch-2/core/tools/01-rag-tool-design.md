# RAG Tool 设计：knowledge_base 工具

## 1. 定位

knowledge_base 是面向 LLM 的文档检索工具。LLM 通过 function calling 调用它，传入检索词，获得相关文档片段和质量反馈。它是 RAG 检索管线（HybridRetriever）与 AgentLoop 之间的桥梁。

## 2. 工具接口

### 2.1 参数定义

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | string | 是 | -- | 检索词 |
| search_type | string | 否 | "hybrid" | 检索策略："hybrid"（语义+关键词）、"semantic"（纯语义）、"keyword"（纯关键词） |
| max_results | int | 否 | 5 | 返回结果数量上限 |
| filter_document_id | string | 否 | null | 限定在某个文档内检索 |

参数设计原则：query 是唯一必填项。其他参数有合理默认值，LLM 大多数情况下只传 query。system prompt 中的检索策略指导会教 LLM 何时使用 search_type 和 max_results。

### 2.2 工具描述

提供给 LLM 的工具描述（tool description）：

```
Search the knowledge base for relevant document content.
Use this tool to find information from uploaded documents.
Parameters:
- query: Search keywords or question (required)
- search_type: "hybrid" (default, best for most queries),
  "semantic" (concept-level matching), "keyword" (exact term matching)
- max_results: Number of results to return (default 5)
- filter_document_id: Restrict search to a specific document (optional)
```

描述使用英文，因为 LLM 的 function calling 训练数据以英文为主，英文描述的指令遵循效果更好。

## 3. 内部流程

```
LLM 传入 query + 参数
    |
[参数解析] 确定 search_type、max_results、filter
    |
[检索路由] 根据 search_type 选择检索器
    |   hybrid   --> HybridRetriever (pgvector + ES 并行, RRF 融合)
    |   semantic --> pgvector retriever (纯语义)
    |   keyword  --> ES retriever (纯 BM25)
    |
[文档过滤] 应用 filter_document_id 和 allowed_doc_ids (notebook scope)
    |
[去重] DeduplicationPostprocessor
    |
[重排序] 可选，由 RAGConfig.rerank_enabled 控制
    |
[结果格式化] 构建 content (给 LLM) + sources (给客户端)
    |
返回 ToolCallResult
```

### 3.1 检索路由

search_type 到检索器的映射：

- **hybrid**：使用 HybridRetriever，pgvector 和 ES 并行检索后 RRF 融合。这是默认策略，适合大多数查询。
- **semantic**：仅使用 pgvector retriever，适合概念性、抽象的查询（如"什么是向量数据库"）。
- **keyword**：仅使用 ES retriever，适合精确术语检索（如"HNSW 算法"）。

三种策略共享相同的后处理管线（去重、过滤、重排序）。

### 3.2 文档过滤

过滤分两层：

- **notebook scope**：allowed_doc_ids 在工具构建时注入，限定检索范围为当前 notebook 下的文档。
- **单文档过滤**：filter_document_id 由 LLM 在调用时传入，进一步限定为某个特定文档。

两层过滤可叠加。

### 3.3 重排序

当 RAGConfig.rerank_enabled=True 时，对融合后的结果进行重排序。重排序器的选择（cross-encoder、LLM-based 等）属于 RAG 管线的配置，不在本工具层面决定。

## 4. 输出设计

### 4.1 content（给 LLM）

返回给 LLM 的文本内容，嵌入质量反馈信号：

```
[检索结果: 共找到 {N} 条相关内容，最高相关度 {max_score}]

[1] 标题: {title} (相关度: {score})
{text_snippet}

[2] 标题: {title} (相关度: {score})
{text_snippet}

...

[提示: {quality_hint}]
```

质量反馈（quality_hint）的生成规则：

| 条件 | 提示内容 |
|------|---------|
| max_score >= 0.8 且结果数 >= 3 | "检索结果质量较高，可以基于以上内容回答。" |
| 0.5 <= max_score < 0.8 | "部分结果相关度一般，如需更精确信息，建议使用更具体的关键词重新检索。" |
| max_score < 0.5 或结果数 = 0 | "检索结果相关度较低或未找到相关内容。建议更换检索词或使用不同的 search_type 重新检索。" |

质量反馈引导 LLM 判断是否需要多轮检索。没有反馈信号时，LLM 要么搜一次就停（信息不足），要么盲目多次检索（浪费迭代）。

### 4.2 sources（给客户端）

从检索结果中提取的 SourceItem 列表，包含完整的元数据：

- document_id：从 node metadata 中提取（使用 extract_document_id 工具函数处理 LlamaIndex 的 metadata 嵌套问题）。
- chunk_id：node_id。
- title：从 metadata 中读取。
- text：node 的完整文本（不截断）。
- score：融合/重排序后的得分。
- source_type："retrieval"。

### 4.3 content 的 token 控制

每个检索结果的 text_snippet 有 token 上限（默认 300 tokens），超出时截断。总 content 有 token 上限（默认 1500 tokens），超出时减少结果数量。

这些限制由 RAGConfig 或工具内部配置控制，不暴露给 LLM。

## 5. Source 提取

AgentLoop 在执行工具后需要从返回值中提取 SourceItem。knowledge_base 工具在注册时附带提取逻辑：

- 工具内部维护 `_last_sources` 属性。
- 每次调用后更新。
- AgentLoop 的 `_execute_tool()` 方法在工具调用后读取此属性。

这替代了当前 es_search_tool.py 中的 `_newbee_es_search_wrapper` + `last_raw_results` 机制。新机制更显式——Source 是工具的标准输出之一，而非通过 side-effect 收集。

## 6. 与现有工具的关系

### 6.1 与 es_search_tool 的关系

当前 es_search_tool 直接对 ES 做 BM25 搜索，独立于 HybridRetriever。重构后 es_search_tool 不再作为独立工具注册，统一为 knowledge_base：

- knowledge_base（search_type="hybrid"）：pgvector 语义检索 + ES 关键词检索，RRF 融合。默认策略，适合大多数查询。
- knowledge_base（search_type="semantic"）：仅 pgvector 语义向量检索，适合概念性、抽象的查询。
- knowledge_base（search_type="keyword"）：仅 ES 关键词匹配，适合精确术语检索。等价于原 es_search_tool 的能力。

RAG（pgvector）和 ES 是两个不同用途的检索后端：RAG 用于语义强化，信息来自向量相似度；ES 用于关键词精确匹配。knowledge_base 的 search_type 参数给 LLM 提供了选择空间，system prompt 中通过检索策略指导强化 LLM 的选择能力。

es_search_tool.py 源文件保留但不注册为工具。

### 6.2 与 Web 搜索工具的关系

Tavily 和智谱的 Web 搜索工具不变。它们与 knowledge_base 工具互补——knowledge_base 检索本地文档，Web 搜索检索互联网内容。两者可以在同一次 AgentLoop 执行中被 LLM 交替调用。

## 7. 构建时机

knowledge_base 工具由 BuiltinToolProvider 在每次 `get_tools()` 调用时新建实例。工具实例的请求级参数绑定流程：

1. ToolRegistry.get_tools(mode, mcp_enabled) -- BuiltinToolProvider 新建工具实例（不含请求级参数）。
2. ModeConfigFactory.build(tools, allowed_document_ids, rag_config, ...) -- 将前端传入的 allowed_document_ids 绑定到 knowledge_base 工具（notebook scope），将 RAGConfig 绑定到工具的检索配置。
3. AgentLoop 执行时，LLM 通过 function calling 传入 query、search_type、filter_document_id 等参数。

参数来源：

| 参数 | 来源 | 注入时机 |
|------|------|---------|
| allowed_doc_ids | 前端"选择检索范围"面板 | ModeConfigFactory 构建时绑定 |
| RAGConfig (top_k, rerank 等) | 请求参数 | ModeConfigFactory 构建时绑定 |
| query | LLM 自主生成 | 工具调用时 |
| search_type | LLM 自主选择 | 工具调用时 |
| filter_document_id | LLM 自主传入 | 工具调用时 |

底层的 HybridRetriever、pgvector index、ES index 是长生命周期的应用级单例，工具实例只是它们之上的轻量级封装。
