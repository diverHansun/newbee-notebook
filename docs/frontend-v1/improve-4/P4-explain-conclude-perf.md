# P4: Explain/Conclude 性能优化

## 问题描述

explain 和 conclude 模式的生成速度明显慢于 chat 和 ask 模式，用户感知到明显的等待。

## 根因分析

explain 和 conclude 模式均使用 `CondensePlusContextChatEngine`，其 `skip_condense` 参数当前设为 `False`（默认值），导致每次请求串行执行三步：

| 步骤 | 操作 | 典型耗时 |
|------|------|---------|
| 1 | **Query Condense**：额外发起一次 LLM 调用，将对话历史压缩为独立查询 | 1-3s |
| 2 | **Hybrid Retrieval**：pgvector 语义检索 + ES BM25 + RRF 融合 | 0.5-1.5s |
| 3 | **Answer Generation**：LLM 流式生成最终回答 | 主要耗时 |

相比之下，chat 模式（FunctionAgent + ES only + fast path）和 ask 模式（两阶段流式，但无 condense 步骤）均无步骤 1 的额外 LLM 调用。

`chat_service.py` 中 explain/conclude 的超时阈值特意放宽至 180s（第 91 行 `STREAM_CHUNK_TIMEOUT_SECONDS_COMPLEX_MODES`），印证了这两个模式的性能预期本就较差。

### 为什么可以禁用 Condense

`skip_condense=True` 意味着不做对话历史压缩，直接将当前查询送入 Hybrid Retriever。

explain 和 conclude 模式的典型调用场景：

- 用户在文档中选中一段文本，点击"解释"或"总结"
- 请求中携带 `context.selected_text`（用户选中文本）和 `context.document_id`
- 查询意图由用户选中内容完全确定，无需压缩历史对话来澄清意图

因此，步骤 1 的 Condense LLM 调用在此场景中是冗余开销。

### top_k 保持 5

Hybrid Retriever 的 `top_k=5` 在现有场景下检索质量可接受，暂不调整，避免影响答案质量。

## 设计方案

### 设计原则

`skip_condense` 直接影响检索质量和响应速度的平衡点，属于运维可调参数，**不得硬编码到代码中**。遵循项目 `configs/` 已有的 YAML 配置惯例，通过 `modes.yaml` 集中管理，`get_modes_config()` 统一读取。

### 第一步：扩展 modes.yaml

在 `newbee_notebook/configs/modes.yaml` 的 `explain` 和 `conclude` 小节中新增 `skip_condense` 字段：

```yaml
# modes.yaml
modes:
  explain:
    engine: query_engine
    retrieval: pgvector
    memory: false
    skip_condense: true   # 新增：跳过 Condense LLM call，节省 1-3s 首 token 延迟
                          # 设为 false 可恢复 condense 步骤（用于对话历史复杂场景）
    description: "Concept explanation and knowledge clarification"

  conclude:
    engine: chat_engine
    retrieval: pgvector
    memory: false
    skip_condense: true   # 新增：同上
    description: "Document summarization and conclusion generation"
```

默认值 `true`，与优化方向一致；若检索质量下降，改回 `false` 即可回滚，**零代码改动**。

### 第二步：config.py 新增读取函数

在 `newbee_notebook/core/common/config.py` 中，`get_modes_config()` 已存在（第 455 行），基于此再追加两个便利函数：

```python
def get_explain_skip_condense() -> bool:
    """从 modes.yaml 读取 explain 模式的 skip_condense 参数。

    Priority order:
    1. configs/modes.yaml (modes.explain.skip_condense)
    2. 默认值 True（优化默认：跳过 condense，降低延迟）
    """
    cfg = get_modes_config()
    return bool(cfg.get("modes", {}).get("explain", {}).get("skip_condense", True))


def get_conclude_skip_condense() -> bool:
    """从 modes.yaml 读取 conclude 模式的 skip_condense 参数。

    Priority order:
    1. configs/modes.yaml (modes.conclude.skip_condense)
    2. 默认值 True
    """
    cfg = get_modes_config()
    return bool(cfg.get("modes", {}).get("conclude", {}).get("skip_condense", True))
```

### 第三步：更新 Mode 实现

在 `explain_mode.py` 中导入配置函数，将硬编码替换为配置读取：

```python
# explain_mode.py
from newbee_notebook.core.common.config import get_explain_skip_condense

# _refresh_engine() 中：
self._chat_engine = CondensePlusContextChatEngine.from_defaults(
    retriever=self._retriever,
    llm=self._llm,
    memory=self._memory,
    system_prompt=self._config.system_prompt or load_prompt("explain.md"),
    skip_condense=get_explain_skip_condense(),  # ← 替换原硬编码 False
    verbose=self._config.verbose,
)
```

`conclude_mode.py` 同理，导入 `get_conclude_skip_condense()`。

> **API 兼容性确认**：实施前先验证已安装的 LlamaIndex 版本是否接受 `skip_condense` 关键字参数（`CondensePlusContextChatEngine.from_defaults` 签名）。若不支持，通过子类重写 `_condense_question()` 方法直接返回原始 query，效果等价，改动约 5 行，`modes.yaml` 配置方式保持不变。

### 预期效果

- 每次 explain/conclude 请求节省约 1-3s 的首 token 延迟（消除 Condense LLM call）
- 检索质量不受影响（Hybrid Retriever 配置不变）
- 超时阈值 `STREAM_CHUNK_TIMEOUT_SECONDS_COMPLEX_MODES = 180` 维持不变
- 回滚成本极低：`modes.yaml` 中 `skip_condense: false` 即可恢复

## 涉及文件

| 文件 | 修改内容 |
|------|----------|
| `newbee_notebook/configs/modes.yaml` | `explain` 和 `conclude` 节新增 `skip_condense: true` |
| `newbee_notebook/core/common/config.py` | 新增 `get_explain_skip_condense()` 和 `get_conclude_skip_condense()` |
| `newbee_notebook/core/engine/modes/explain_mode.py` | `_refresh_engine()` 中读取配置替换硬编码 `False` |
| `newbee_notebook/core/engine/modes/conclude_mode.py` | 同上 |

## 验证标准

- explain/conclude 首 token 到达时间（TTFT）与修改前相比缩短至少 1s
  - 测量方法：后端日志中对比 `start` 事件到第一个 `content` 事件的时间戳差值
- 回答质量不下降（使用相同问题对比修改前后的 `source_nodes` 和回答内容）
- chat 和 ask 模式行为不受影响
- 将 `modes.yaml` 中 `skip_condense` 改为 `false` 后，行为恢复同修改前（回滚验证）
- `python -m pytest newbee_notebook/tests/unit/test_modes.py` 通过

## 后续观察

若 `skip_condense: true` 后出现检索质量下降（`source_nodes` 相关性明显变差），直接将 `modes.yaml` 中对应字段改回 `false` 即可，无需修改任何代码。如需更细粒度控制，可在 mode 层判断 `context.selected_text` 是否非空，有选中文本时跳过 condense，无选中文本时恢复——此为后续优化方向，不在 P4 范围内。
