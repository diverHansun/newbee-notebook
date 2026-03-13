# Engine 模块：检索质量门控

## 1. 目标

`Explain / Conclude` 需要由后端规则决定：

- 是否可以提前结束检索
- 是否需要继续下一轮检索
- 是否允许从当前文档放宽到 notebook scope

这部分不完全交给 LLM 自己判断。

## 2. 设计原则

### 2.1 由工具提供标准化质量信号

runtime 不直接对比不同检索策略的原始分数。

原因：

- `keyword / semantic / hybrid` 的 raw score 不同质
- 直接在 engine 中比较 raw score 会让调参失控

因此由 `knowledge_base` 在每次调用后返回 `quality_meta`，engine 只消费标准化结果。

### 2.2 规则优先，模型辅助

批量一版使用可解释的后端规则：

- 高质量：可提前 synthesis
- 中低质量：继续检索或放宽范围
- 达到上限：强制 synthesis

LLM 可以调整 query 和部分参数，但不能绕开质量门控。

## 3. `quality_meta` 协议

每次 `knowledge_base` 调用后，工具返回：

```json
{
  "scope_used": "document",
  "search_type": "keyword",
  "result_count": 4,
  "max_score": 0.71,
  "quality_band": "high",
  "scope_relaxation_recommended": false
}
```

字段说明：

| 字段 | 含义 |
|------|------|
| `scope_used` | 本次检索实际使用的范围：`document` 或 `notebook` |
| `search_type` | 实际检索策略：`keyword` / `semantic` / `hybrid` |
| `result_count` | 有效结果数量 |
| `max_score` | 供日志和调试使用的最高分 |
| `quality_band` | 归一化质量等级：`high` / `medium` / `low` / `empty` |
| `scope_relaxation_recommended` | 工具层是否建议放宽范围 |

## 4. Explain 默认门控

Explain 要求更贴近选中文本，因此门控更严格。

### 4.1 质量分段

推荐默认规则：

- `high`
  - `result_count >= 2`
  - 且存在明显高相关结果
- `medium`
  - 有结果，但聚焦度一般
- `low`
  - 有结果，但相关性明显不足
- `empty`
  - 无有效结果

### 4.2 决策规则

| iteration | scope | 质量 | 决策 |
|-----------|-------|------|------|
| 1 | `document` | `high` | 进入 synthesis |
| 1 | `document` | `medium/low/empty` | 进入 iteration 2，可放宽到 `notebook` |
| 2 | `document/notebook` | `high` | 进入 synthesis |
| 2 | `document/notebook` | `medium/low/empty` | 进入 iteration 3 |
| 3 | 任意 | 任意 | 强制 synthesis |

## 5. Conclude 默认门控

Conclude 允许更大的覆盖范围，因此门控更宽松。

### 5.1 质量分段

推荐默认规则：

- `high`
  - `result_count >= 3`
  - 且整体覆盖较完整
- `medium`
  - 结果可用，但仍可能需要补充
- `low`
  - 结果过少或过散
- `empty`
  - 无有效结果

### 5.2 决策规则

| iteration | scope | 质量 | 决策 |
|-----------|-------|------|------|
| 1 | `document` | `high` | 进入 synthesis |
| 1 | `document` | `medium` | 可直接 synthesis，或进入 iteration 2 |
| 1 | `document` | `low/empty` | 进入 iteration 2，可放宽到 `notebook` |
| 2 | `document/notebook` | `high` | 进入 synthesis |
| 2 | `document/notebook` | `medium/low/empty` | 进入 iteration 3 |
| 3 | 任意 | 任意 | 强制 synthesis |

第一版建议实现为：

- `medium` 默认仍继续到下一轮，除非模型明确表达“信息已足够”

这样更稳，不会过早截断总结上下文。

## 6. Scope 放宽规则

Explain / Conclude 只允许一种放宽路径：

```text
document -> notebook
```

触发条件：

- `quality_band` 不是 `high`
- 且 `allow_scope_relaxation = true`
- 且当前 scope 仍为 `document`

禁止：

- `document -> global`
- `notebook -> web`
- `notebook -> MCP`

## 7. Engine 决策接口

建议 engine 内部不要直接判断原始分数，而只消费：

- `quality_band`
- `scope_used`
- `iteration_index`

伪代码：

```python
if quality_band == "high":
    return SYNTHESIZE
if scope_used == "document" and allow_scope_relaxation:
    return CONTINUE_WITH_NOTEBOOK_SCOPE
if iteration_index < max_retrieval_iterations:
    return CONTINUE
return FORCE_SYNTHESIZE
```

## 8. 可观测性

每次 `tool_result` 事件都建议带上精简后的 `quality_meta`，至少包含：

- `scope_used`
- `search_type`
- `result_count`
- `quality_band`

这样前后端和测试都能看到 runtime 为什么继续检索或提前 synthesis。
