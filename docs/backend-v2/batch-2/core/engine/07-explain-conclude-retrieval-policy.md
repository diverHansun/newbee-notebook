# Engine 模块：Explain / Conclude 检索策略

## 1. 适用范围

本策略仅适用于：

- `explain`
- `conclude`

两者都由文档阅读器中的选中文本触发，不再走 LlamaIndex `QueryEngine`。

## 2. 核心原则

### 2.1 一次前端触发 = 一次请求

用户在 markdown viewer 中选中文本并点击 `Explain` 或 `Conclude`，对应一次完整请求。

这次请求内部允许多个 retrieval iteration，但对前端来说仍然是一轮对话。

### 2.2 每次 retrieval iteration 都必须调用 `knowledge_base`

这是 runtime 的硬约束，不依赖 prompt 自觉。

如果某一轮输出：

- 没有工具调用
- 调用了错误工具
- 工具参数不可解析

runtime 必须触发 repair，而不是直接进入最终回答。

### 2.3 retrieval 与 synthesis 分离

Explain / Conclude 的执行不是“边检索边出最终文本”，而是两阶段：

1. `retrieval iterations`
2. `final_synthesis`

`final_synthesis` 阶段不允许再调工具，只负责基于已有检索结果回答。

## 3. 执行流程

```text
prepare input
-> iteration 1: knowledge_base (document scope)
-> quality check
-> iteration 2: knowledge_base (document or notebook scope)
-> quality check
-> iteration 3: knowledge_base (document or notebook scope)
-> quality check
-> final_synthesis
```

### 3.1 提前结束

如果第 1 或第 2 次 retrieval 后命中“信息足够”规则，可以提前结束检索并进入 synthesis。

### 3.2 强制结束

如果已到第 3 次 retrieval iteration，无论检索质量如何，都必须进入 synthesis。

## 4. 输入构造

### 4.1 `selected_text`

`selected_text` 是 Explain / Conclude 的核心输入，不是普通附加上下文。

它必须参与：

- query 模板生成
- system prompt 提示
- 最终回答上下文

### 4.2 `message`

`message` 是可选补充项，用于表达：

- 想解释的重点
- 想总结的角度
- 输出格式偏好

如果 `message` 为空，runtime 使用默认指令。

## 5. 默认参数模板

后端为 Explain / Conclude 提供默认模板，LLM 可以覆盖可变字段，但不能突破 mode policy 的硬约束。

## 5.1 Explain 默认模板

### iteration 1

```json
{
  "query": "<selected_text> + <message_or_default_instruction>",
  "search_type": "keyword",
  "max_results": 4,
  "filter_document_id": "<current_document_id>"
}
```

### iteration 2

```json
{
  "query": "<selected_text> + <message_or_refined_focus>",
  "search_type": "semantic",
  "max_results": 4,
  "filter_document_id": "<current_document_id_or_relaxed>"
}
```

### iteration 3

```json
{
  "query": "<selected_text> + <message_or_refined_focus>",
  "search_type": "hybrid",
  "max_results": 5,
  "filter_document_id": "<current_document_id_or_relaxed>"
}
```

Explain 默认更偏精确命中和局部解释，因此优先使用 `keyword / semantic`。

## 5.2 Conclude 默认模板

### iteration 1

```json
{
  "query": "<selected_text> + <message_or_default_instruction>",
  "search_type": "hybrid",
  "max_results": 6,
  "filter_document_id": "<current_document_id>"
}
```

### iteration 2

```json
{
  "query": "<selected_text> + <message_or_summary_focus>",
  "search_type": "hybrid",
  "max_results": 8,
  "filter_document_id": "<current_document_id_or_relaxed>"
}
```

### iteration 3

```json
{
  "query": "<selected_text> + <message_or_summary_focus>",
  "search_type": "semantic",
  "max_results": 8,
  "filter_document_id": "<current_document_id_or_relaxed>"
}
```

Conclude 默认更偏覆盖面，因此优先使用 `hybrid`，并允许更大的 `max_results`。

## 6. Scope 策略

### 6.1 初始范围

Explain / Conclude 的第一轮检索都必须从当前文档开始：

```text
scope = document
filter_document_id = context.document_id
```

### 6.2 放宽范围

只有在质量门控判定“不足”时，才允许放宽：

```text
document -> notebook
```

不允许：

- `document -> global`
- `document -> web`
- `document -> MCP`

## 7. repair 策略

当模型没有遵守每轮必须调用 `knowledge_base` 的规则时：

1. runtime 追加 repair message
2. 要求模型重新生成本轮工具调用
3. repair 次数超过上限后返回错误

推荐默认值：

- `invalid_tool_repair_limit = 2`

## 8. synthesis 规则

进入 `final_synthesis` 后：

- 工具调用被禁用
- 仅使用当前消息链和检索结果回答
- 产出流式 `content` 事件
- 最终统一返回 `sources`

这保证 Explain / Conclude 的输出是 grounded 的，同时不会陷入无限检索循环。
