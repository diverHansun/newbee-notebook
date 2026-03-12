# Context 模块：验证策略

## 1. 测试范围

| 测试对象 | 覆盖 |
|---------|------|
| SessionMemory 双轨读写 | 是 |
| 可见性规则 | 是 |
| Side 轨道容量裁剪 | 是 |
| ContextBuilder 消息链构建 | 是 |
| 分层压缩（完整/压缩/摘要） | 是 |
| 工具结果压缩 | 是 |
| TokenCounter 统计准确性 | 是 |
| ContextBudget 预算分配 | 是 |
| 从持久化消息恢复 | 是 |

| 排除对象 | 理由 |
|---------|------|
| LLM 摘要的语义质量 | 属于 LLM 能力评估，非本模块职责 |
| tokenizer 对特定语言的精度 | 属于 LLM Provider 的职责 |
| 消息持久化 | 属于 session 模块 |

## 2. 关键场景

### 2.1 双轨隔离

**场景：Agent 和 Ask 共享 Main 轨道**

向 Main 轨道以 Agent 模式追加消息，再以 Ask 身份读取。验证 Ask 可以看到 Agent 的消息。

**场景：Side 可读 Main，Main 不可读 Side**

向 Main 追加消息，向 Side 追加消息。以 Side 身份构建消息链，验证包含 Main 历史。以 Main 身份构建消息链，验证不包含 Side 消息。

**场景：Side 轨道容量裁剪**

配置 Side 上限为 3 轮。向 Side 追加 5 轮交互。验证 Side 只保留最近 3 轮，且裁剪是成对的（无孤立 user 或 assistant 消息）。

### 2.2 分层压缩

**场景：历史未超预算，不压缩**

Main 轨道有 3 轮对话，token 数远低于预算。构建消息链，验证所有消息完整保留，无截断或摘要。

**场景：历史触发压缩层**

Main 轨道有 8 轮对话（超过完整层 N=5 但未超过 N+M=15）。构建消息链，验证最近 5 轮完整保留，第 6-8 轮的 assistant 消息被提取首段。

**场景：历史触发摘要层**

Main 轨道有 20 轮对话。首次构建消息链时无摘要缓存，验证使用截断版本。触发异步摘要生成后，第二次构建验证使用摘要文本。

**场景：摘要过期后重新生成**

有缓存摘要的情况下追加新消息使得摘要范围扩大。验证摘要被标记为过期，下次构建使用截断版，异步重新生成。

### 2.3 工具结果压缩

**场景：多轮工具调用的差异化处理**

消息链中包含 3 轮 tool_result 消息。调用 compress_tool_results，验证最后一轮的 content 完整保留，前两轮的 content 被截断到预算上限。

### 2.4 Token 预算

**场景：预算分配正确性**

给定总预算和各项配置，验证 ContextBudget 的计算结果：固定项扣除后的剩余预算正确分配给历史层级。

**场景：消息链在预算内**

构建消息链后，用 TokenCounter 统计总 token 数，验证不超过 total 预算。

### 2.5 恢复

**场景：从持久化消息恢复**

构造 Message 实体列表（含 Chat/Ask/Explain/Conclude 四种 mode），调用 load_from_messages，验证 Chat/Ask 消息进入 Main 轨道，Explain/Conclude 进入 Side 轨道。

**场景：恢复后摘要加载**

提供 context_summary 字符串，验证恢复后 get_summary() 返回该摘要。

## 3. 验证方法

### 3.1 单元测试

使用 pytest + pytest-asyncio。

Mock 策略：
- LLM：mock tokenizer 返回固定 token 数（便于预算计算的确定性测试）。
- Compressor 的 summarize 方法：mock LLM 调用返回固定摘要文本。

测试文件：
```
tests/unit/core/context/
    test_session_memory.py      双轨读写、容量裁剪、恢复
    test_context_builder.py     消息链构建、分层压缩、工具结果压缩
    test_token_counter.py       token 统计准确性
    test_budget.py              预算分配计算
    test_compressor.py          截断、首段提取、摘要生成
```
