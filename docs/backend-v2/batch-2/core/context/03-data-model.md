# Context 模块：核心概念与数据模型

## 1. 设计阶段划分

batch-2 的 context 模块分两层：

### 1.1 第一版必须实现

- 双轨内存（Main / Side）
- OpenAI-compatible 内部消息模型
- 确定性截断
- 基础 token 预算
- session lock 协作

### 1.2 后续增强

- 分层压缩
- 异步摘要
- 更细的预算分配
- 摘要缓存失效机制

第一版先满足可迁移、可测试、可控。

## 2. `SessionMemory`

`SessionMemory` 是双轨内存容器，存储一个 session 的对话历史。

### 2.1 轨道定义

| 轨道 | 写入来源 |
|------|---------|
| `main` | `agent`, `ask` |
| `side` | `explain`, `conclude` |

### 2.2 可见性规则

| 读取方 | 可见内容 |
|--------|---------|
| `agent / ask` | `main` |
| `explain / conclude` | `side` + 截断后的 `main` 注入 |

Explain / Conclude 读取 Main 轨道时是只读注入，不回写 Main。

## 3. `InternalMessage`

Context 模块不再产出 `LlamaIndex ChatMessage`。

它产出统一的 OpenAI-compatible internal message：

```python
class InternalMessage(TypedDict, total=False):
    role: str
    content: str | list[dict] | None
    tool_calls: list[dict]
    tool_call_id: str
    metadata: dict
```

### 3.1 允许的角色

- `system`
- `user`
- `assistant`
- `tool`

### 3.2 存储与构建的区别

- `SessionMemory` 可存储简化后的业务消息
- `ContextBuilder` 负责把这些业务消息转成完整 `InternalMessage` 列表

因此 context 对持久化结构和 runtime 结构做一次受控转换。

### 3.3 Context 只接收 canonical business history

第一版明确限制：

- `SessionMemory` 不存储 `assistant(tool_calls)`
- `SessionMemory` 不存储 `tool`
- `SessionMemory` 不存储 `reasoning_content`

也就是说，ContextBuilder 的历史输入只来自：

- `user`
- `assistant(final)`

工具调用链与 provider thinking 都只属于 request-scoped runtime，不属于持久化上下文。

## 4. `ContextBudget`

第一版预算结构保留简单版：

| 字段 | 含义 |
|------|------|
| `total` | 可用总预算 |
| `system_prompt` | system prompt 预留 |
| `history` | 历史消息预算 |
| `current_message` | 当前用户消息预算 |
| `tool_results` | 当前请求内工具结果预算 |
| `output_reserved` | 预留给模型输出的预算 |
| `main_injection` | Main 注入 Side 的预算 |

后续再拆更细层级。

## 5. `ContextBuilder`

`ContextBuilder` 负责把当前 session 状态构造成最终消息链。

输入：

- `SessionMemory`
- 当前 mode
- `system_prompt`
- 当前 user message
- budget

输出：

- `list[InternalMessage]`

它是纯函数式组件：

- 不直接写回 memory
- 不持有跨请求状态

## 6. 截断策略

第一版统一采用确定性截断：

- 从最近消息向前保留
- 在 token 预算内尽量保留完整 turn
- 必要时对较早 assistant 内容做截断

这比一开始就引入摘要更容易验证，也更适合 batch-2 的大迁移阶段。

## 7. `Compressor`

第一版 `Compressor` 只要求实现轻量能力：

- 文本截断
- 首段提取

摘要生成保留为后续增强项，不作为批量一版阻塞条件。

## 8. 生命周期

### 8.1 `SessionMemory`

与 session 生命周期绑定。

### 8.2 `ContextBuilder`

每次请求构建一次，无跨请求状态。

### 8.3 `Compressor`

纯工具组件，可被 `ContextBuilder` 调用。

## 9. 与 provider transient signals 的边界

context 模块不直接处理：

- `reasoning_content`
- `thinking`
- provider-specific stream delta

这些内容由 `llm` 和 `engine` 在请求期消费，不能进入 session 持久化历史。
