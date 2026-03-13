# RAG Tool 设计：`knowledge_base`

## 1. 定位

`knowledge_base` 是 batch-2 的核心检索工具：

- 供 `ask / explain / conclude` 使用
- 未来也供 `agent` 使用
- 统一承接本地知识库检索，不再让 Ask/Explain/Conclude 各自包一套检索逻辑

## 2. 参数定义

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `query` | string | 是 | -- | 检索词 |
| `search_type` | string | 否 | `hybrid` | `hybrid / semantic / keyword` |
| `max_results` | int | 否 | 5 | 返回结果数上限 |
| `filter_document_id` | string | 否 | null | 限制在当前文档内检索 |

### 2.1 参数来源

- 模型显式传入：`query / search_type / max_results / filter_document_id`
- runtime 隐式注入：`allowed_document_ids / notebook scope / request_rag_config`

这两层参数必须分开，不能要求模型感知所有内部约束。

## 3. 模式偏好

| mode | 默认偏好 |
|------|----------|
| `ask` | notebook scope，优先 `knowledge_base` |
| `explain` | 当前文档 scope，优先精确 / 搜索型 |
| `conclude` | 当前文档 scope，优先 `hybrid`，更大 `max_results` |

Explain / Conclude 的强约束由 engine policy 保证，不由工具本身负责。

## 4. 内部流程

```text
参数解析
-> scope 解析
-> 选择检索路由
-> 应用 notebook/document 过滤
-> 后处理 / 去重 / 可选重排
-> 生成 content + sources + quality_meta
```

### 4.1 检索路由

- `hybrid`：pgvector + ES 融合
- `semantic`：纯语义检索
- `keyword`：纯关键词检索

### 4.2 Scope

- notebook scope：由 runtime 通过 `allowed_document_ids` 注入
- document scope：由 `filter_document_id` 表达

两者可叠加。

## 5. 输出结构

`knowledge_base` 必须返回统一的 `ToolCallResult`：

```python
{
  "content": "...",
  "sources": [...],
  "quality_meta": {...}
}
```

### 5.1 `content`

给模型继续推理的文本内容，应包含：

- 检索摘要
- 命中的片段
- 足够的结构化提示，帮助模型判断是否继续检索

### 5.2 `sources`

给前端展示的统一来源列表，使用 `SourceItem` 协议。

### 5.3 `quality_meta`

给 runtime 做门控和 scope 放宽判断的标准化信号，详细见：

- [../engine/08-retrieval-quality-gates.md](../engine/08-retrieval-quality-gates.md)

## 6. 为什么不再使用 side-effect 收集来源

当前实现通过 wrapper 或缓存属性旁路收集 sources。batch-2 不再保留这种设计。

新要求：

- `sources` 是工具返回值的正式字段
- `quality_meta` 是工具返回值的正式字段
- runtime 不再依赖 `_last_sources` 之类的隐式状态

这对 Ask、Explain、Conclude 和未来 MCP 工具都更稳定。
