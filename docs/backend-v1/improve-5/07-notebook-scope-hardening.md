# Improve-5 补充：Notebook 作用域收敛与检索一致性

## 1. 目标

在 improve-5 已完成的状态机与降级链路基础上，补齐检索作用域一致性，确保 `chat/ask/explain/conclude` 四模式在 RAG/ES 过程中都严格限定在当前 Notebook 文档集合。

## 2. 补充问题

1. `chat` 模式的来源收集存在“检索后未做 allowed_doc_ids 后过滤”的窗口。
2. `conclude` 模式此前使用 pgvector retriever 直连，未与 `ask/explain` 保持同等后过滤策略。
3. `knowledge_base_search`（Chat ES tool）默认是全局索引检索，可能引入非 Notebook 文档。
4. `Skipping source with missing document_id` 在单次请求中会重复打印，日志噪声较大。
5. `ask` 模式在“严格 notebook 作用域 + 泛化英文提问”场景下，可能出现首轮检索 0 命中，`sources` 为空。

## 3. 方案

### 3.1 `chat` / `conclude` 过滤补齐

1. `chat`：在 `_collect_sources` 中对检索结果按 `allowed_doc_ids` 再过滤。
2. `conclude`：新增 `ScopedRetriever` 包装器，对检索结果执行统一后过滤后再送入 QueryEngine。

### 3.2 Chat ES tool notebook 作用域

1. `build_tool_registry` 支持注入 `allowed_doc_ids`。
2. `knowledge_base_search` 支持 notebook 作用域：
   - 查询层增加 metadata terms filter（预过滤）。
   - 返回层再按 document_id 后过滤（双保险）。
3. `ChatMode` 在作用域变化时刷新工具实例，避免沿用旧作用域。
4. 空作用域语义保真：`allowed_doc_ids=[]` 时保持“空结果”而不是退化到全局检索。

### 3.3 warning 优化

1. `ChatService._filter_valid_sources` 对同一缺失 `document_id` 聚合告警（带计数）。
2. 单次请求内同一 doc_id 仅告警一次，避免刷屏。

### 3.4 Ask 空召回兜底（title-boost retry）

1. `AskMode` 在首轮检索为空时，使用 `allowed_document_titles`（由 ChatService 注入）构造一次增强查询重试。
2. 增强策略保持最小化：仅拼接前 2 个标题，不改动 notebook 作用域过滤语义。
3. 若重试仍为空，返回空 sources（保持“严格作用域 + 真实召回结果”）。

## 4. 一致性目标（四模式）

1. `ask`：`HybridRetriever` + `allowed_doc_ids` 后过滤 + 空召回 title-boost 单次重试。
2. `explain`：`HybridRetriever` + `allowed_doc_ids` 后过滤（保持既有逻辑）。
3. `chat`：来源收集 + ES tool 均受 notebook 作用域约束。
4. `conclude`：检索器层统一后过滤，确保总结上下文仅来自 notebook 文档。

## 5. API/测试资产补充

1. Postman 补充 `DELETE /api/v1/library/documents/{document_id}?force=true` 用例。
2. 保持并强调 `DELETE /api/v1/notebooks/{notebook_id}/documents/{document_id}` 仅取消关联，不删除 Library 文档。
