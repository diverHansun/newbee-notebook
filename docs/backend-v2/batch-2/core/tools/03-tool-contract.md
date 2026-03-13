# Tools 模块：统一工具协议

## 1. 目标

batch-2 之后，工具层不再依赖：

- LlamaIndex `BaseTool`
- 各 mode 自己维护的 side-effect 包装
- ChatMode / AskMode 各自定制的 source 收集逻辑

统一使用一套显式 contract：

- `ToolDefinition`
- `ToolCallResult`
- `SourceItem`
- `ToolQualityMeta`

## 2. `ToolDefinition`

`ToolDefinition` 是 runtime 可直接执行的工具定义。

```python
class ToolDefinition(TypedDict):
    name: str
    description: str
    parameters: dict
    execute: Callable[[dict, "ToolExecutionContext"], Awaitable["ToolCallResult"]]
```

### 2.1 字段说明

| 字段 | 含义 |
|------|------|
| `name` | 工具名称，对应 OpenAI function name |
| `description` | 提供给模型的工具说明 |
| `parameters` | JSON Schema，定义可调用参数 |
| `execute` | 统一异步执行函数 |

### 2.2 为什么统一 async

第一版直接规定 `execute()` 为异步接口。

原因：

- 内置工具里已经包含异步 I/O
- MCP 工具天然是异步
- 统一后 engine 不需要区分 sync / async 路径

## 3. `ToolExecutionContext`

工具执行需要请求级上下文，但这些信息不应混进模型可见参数。

建议最小上下文：

```python
class ToolExecutionContext(TypedDict, total=False):
    mode: str
    notebook_id: str
    session_id: str
    current_document_id: str
    allowed_document_ids: list[str]
    request_rag_config: dict
```

这让工具能够拿到：

- notebook scope
- 当前文档范围
- 请求级 RAG 参数

同时避免要求模型显式重复传入所有内部控制参数。

## 4. `ToolCallResult`

所有工具都返回统一结构：

```python
class ToolCallResult(TypedDict, total=False):
    content: str
    sources: list["SourceItem"]
    quality_meta: "ToolQualityMeta"
    error: "ToolError"
    metadata: dict
```

### 4.1 字段说明

| 字段 | 说明 |
|------|------|
| `content` | 写回消息链给模型继续推理的文本 |
| `sources` | 给前端展示的统一引用列表 |
| `quality_meta` | 检索类工具返回的标准化质量信号 |
| `error` | 工具失败时的结构化错误 |
| `metadata` | 额外调试或统计字段，不直接暴露给前端 |

### 4.2 约束

- `content` 允许为空字符串，但不能为 `None`
- `sources` 默认为空列表
- 工具失败时仍允许返回部分 `sources`
- `quality_meta` 仅对检索型工具强制要求，其他工具可省略

## 5. `SourceItem`

统一 source 协议如下：

```python
class SourceItem(TypedDict, total=False):
    document_id: str
    chunk_id: str
    title: str
    text: str
    score: float
    source_type: str
    metadata: dict
```

### 5.1 `source_type`

第一版保留这些取值：

- `retrieval`
- `keyword`
- `web_search`
- `mcp`

前端只消费一套 sources 列表，不再为 chat / ask / explain 维护不同结构。

## 6. `ToolQualityMeta`

检索型工具的标准质量信号：

```python
class ToolQualityMeta(TypedDict, total=False):
    scope_used: str
    search_type: str
    result_count: int
    max_score: float
    quality_band: str
    scope_relaxation_recommended: bool
```

`knowledge_base` 必须返回该结构；其他工具可选。

## 7. `ToolError`

建议结构：

```python
class ToolError(TypedDict, total=False):
    code: str
    message: str
    retriable: bool
```

runtime 对工具错误的处理规则：

- 将错误写回 tool result
- 由 Agent runtime 决定是 repair、重试还是继续推理

## 8. OpenAI Function Tool 映射

`ToolDefinition` 到 OpenAI function tool 的映射：

```python
{
  "type": "function",
  "function": {
    "name": tool.name,
    "description": tool.description,
    "parameters": tool.parameters
  }
}
```

因此 tools 模块的内部协议与 OpenAI SDK 消息协议天然对齐，不再需要 LlamaIndex 的额外转换层。

## 9. `knowledge_base` 特殊约束

`knowledge_base` 是 batch-2 的核心工具，额外要求：

- 必须返回 `quality_meta`
- `content` 与 `sources` 语义一致
- 必须尊重 runtime 注入的 scope 参数
- Explain / Conclude 模式下只允许它作为唯一工具

## 10. MCP 兼容

MCP 工具通过 adapter 转换为同样的 `ToolDefinition`。

约束：

- MCP 工具可以没有 `sources`
- MCP 工具一般没有 `quality_meta`
- 但仍必须返回统一的 `ToolCallResult`

这样 `ToolRegistry` 才能把内置工具和 MCP 工具无差别交给 runtime。
