# Engine 模块：核心概念与数据模型

## 1. `ModeConfig`

`ModeConfig` 是 workflow runtime 的单次请求配置对象。

它不再只是“system prompt + tools + user_message”的轻量包装，而是 mode 语义的正式载体。

建议结构：

```python
class ModeConfig(TypedDict):
    mode_name: str
    system_prompt: str
    user_message: dict
    loop_policy: LoopPolicy
    tool_policy: ToolPolicy
    synthesis_policy: dict
    source_policy: dict
```

## 2. `LoopPolicy`

`LoopPolicy` 负责定义“这次请求怎么跑”。

建议字段：

| 字段 | 含义 |
|------|------|
| `execution_style` | `open_loop` 或 `retrieval_required_loop` |
| `max_total_iterations` | 整个请求的安全熔断 |
| `max_retrieval_iterations` | Explain / Conclude 的检索迭代上限 |
| `required_tool_name` | 例如 `knowledge_base` |
| `require_tool_every_iteration` | 当前模式是否每轮都必须调工具 |
| `invalid_tool_repair_limit` | 非法工具输出的修复上限 |
| `allow_early_synthesis` | 质量足够时是否允许提前 synthesis |
| `force_synthesis_after_limit` | 到上限后是否强制进入 synthesis |
| `emit_tool_events` | 是否输出结构化工具事件 |

推荐默认值：

| mode | execution_style | max_total_iterations | max_retrieval_iterations | required_tool_name |
|------|-----------------|----------------------|--------------------------|--------------------|
| `agent` | `open_loop` | 50 | 0 | -- |
| `ask` | `open_loop` | 50 | 0 | -- |
| `explain` | `retrieval_required_loop` | 12 | 3 | `knowledge_base` |
| `conclude` | `retrieval_required_loop` | 12 | 3 | `knowledge_base` |

## 3. `ToolPolicy`

`ToolPolicy` 负责定义“能用什么工具、默认怎么用、scope 怎么控制”。

建议字段：

| 字段 | 含义 |
|------|------|
| `allowed_tool_names` | 当前 mode 允许的工具集合 |
| `default_tool_name` | 默认首选工具 |
| `default_tool_args_template` | 后端提供的默认参数模板 |
| `llm_can_override_fields` | 允许模型覆盖的字段 |
| `initial_scope` | `document` / `notebook` / `mixed` |
| `allow_scope_relaxation` | 是否允许放宽检索范围 |
| `scope_relaxation_rule` | 例如 `document -> notebook` |
| `quality_gate` | 检索质量门控规则 |

推荐默认值：

| mode | allowed_tool_names | default_tool_name | initial_scope |
|------|--------------------|-------------------|---------------|
| `agent` | 由 ToolRegistry 返回 | -- | `mixed` |
| `ask` | `knowledge_base`, `time` | `knowledge_base` | `notebook` |
| `explain` | `knowledge_base` | `knowledge_base` | `document` |
| `conclude` | `knowledge_base` | `knowledge_base` | `document` |

## 4. 请求级输入模型

### 4.1 `RuntimeRequest`

```python
class RuntimeRequest(TypedDict, total=False):
    mode: str
    message: str
    session_id: str
    notebook_id: str
    source_document_ids: list[str]
    rag_config: dict
    context: dict
```

### 4.2 `context`

Explain / Conclude 依赖的最小上下文：

```python
{
  "selected_text": "...",
  "document_id": "...",
  "chunk_id": "...",
  "page_number": 12
}
```

校验规则：

- `agent / ask`：`message` 必填
- `explain / conclude`：`context.selected_text` 和 `context.document_id` 必填，`message` 可选

## 5. 内部消息格式

runtime 使用 OpenAI-compatible message schema，详细约定见：

- [llm/06-message-contract.md](../llm/06-message-contract.md)

本模块只依赖四种角色：

- `system`
- `user`
- `assistant`
- `tool`

补充边界：

- `engine` 只消费 canonical messages
- `reasoning_content / thinking` 属于 provider transient signal
- `engine` 可以把 transient signal 映射成 `phase / thinking` 事件，但不能把它们写成业务消息

## 6. `StreamEvent`

统一事件集合：

| 事件 | 用途 |
|------|------|
| `start` | 请求开始 |
| `warning` | 非阻断提示 |
| `phase` | 运行阶段变化 |
| `tool_call` | 工具调用开始 |
| `tool_result` | 工具执行完成 |
| `sources` | 统一来源列表 |
| `content` | 最终回答的文本增量 |
| `done` | 请求结束 |
| `error` | 请求失败 |
| `heartbeat` | API 层保活 |

### 6.1 `phase`

推荐阶段值：

- `reasoning`
- `retrieving`
- `synthesizing`

`thinking` 仅作为兼容旧前端的 alias，不再作为文档中的正式协议名称。

### 6.2 tool-using 请求的 thinking 策略

对于 batch-2 第一版的 tool-using requests：

- `agent`
- `ask`
- `explain`
- `conclude`

runtime 默认不依赖 provider thinking mode 作为核心执行能力。

更具体地说：

- OpenAI-compatible `tool_calls` 是主执行信号
- `reasoning_content` 只作为可选观测信息
- provider-specific thinking 差异由 `LLMClient` 吸收，而不是由 `AgentLoop` 直接分支处理

## 7. `ToolCallResult`

`ToolCallResult` 由 tools 模块正式定义，engine 只消费该结构。

核心字段：

- `content`
- `sources`
- `quality_meta`
- `error`

详细约定见：

- [tools/03-tool-contract.md](../tools/03-tool-contract.md)

## 8. `SourceItem`

前端统一消费的一条来源结构：

| 字段 | 含义 |
|------|------|
| `document_id` | 来源文档 ID |
| `chunk_id` | 片段 ID |
| `title` | 标题 |
| `text` | 片段文本 |
| `score` | 检索分数 |
| `source_type` | `retrieval` / `keyword` / `web_search` / `mcp` |

这套协议在四个模式之间保持一致。
