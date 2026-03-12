# Context 模块：核心概念与数据模型

## 1. SessionMemory

SessionMemory 是双轨内存容器，存储一个 Session 内的全部对话消息。

### 1.1 轨道定义

| 轨道 | 写入来源 | 消息格式 |
|------|---------|---------|
| Main | Agent 模式、Ask 模式 | LlamaIndex ChatMessage（role=user/assistant） |
| Side | Explain 模式、Conclude 模式 | LlamaIndex ChatMessage（role=user/assistant） |

每条轨道内部按时间顺序存储消息，user 和 assistant 消息成对出现。

### 1.2 可见性规则

| 读取方 | 可见内容 |
|--------|---------|
| Agent/Ask | Main 轨道 |
| Explain/Conclude | Main 轨道（只读，截断后） + Side 轨道 |

"只读"含义：Explain/Conclude 的执行结果不写入 Main 轨道。Main 轨道对 Side 轨道的操作无感知。

### 1.3 容量管理

Main 轨道没有硬性的轮次上限，通过分层压缩控制 token 占用。

Side 轨道设置轮次上限（默认 10 轮，即 20 条消息）。超出时裁剪最早的交互对。裁剪以交互对（user + assistant）为最小单位，保持消息链的完整性。

### 1.4 恢复

SessionMemory 支持从持久化消息列表重建。session 模块从数据库加载 Message 实体列表后，按 mode 分类传入 SessionMemory，由 SessionMemory 将其转换为 ChatMessage 并写入对应轨道。

## 2. ContextBudget

ContextBudget 定义消息链各部分的 token 预算分配方案。

### 2.1 预算项

| 预算项 | 说明 | 参考默认值 |
|--------|------|-----------|
| total | 总预算（模型上下文窗口的可用比例） | 模型窗口 * 0.6 |
| system_prompt | system prompt 预留 | 800 |
| history_summary | 摘要层预算 | 2000 |
| history_compressed | 压缩层预算 | 4000 |
| history_full | 完整层预算 | 8000 |
| tool_results | 当前请求内工具结果总预算 | 4000 |
| current_message | 当前用户消息预留 | 动态（实际消息长度） |
| output_reserved | LLM 输出预留 | 4000 |
| main_injection | Main 历史注入 Side 的预算 | 3000 |

默认值是初始参考，可通过配置文件调整。total 预算根据实际使用的 LLM 模型的上下文窗口动态计算。

### 2.2 预算计算

构建消息链时，ContextBuilder 按以下优先级分配预算：

1. 固定项先扣除：system_prompt + output_reserved + current_message
2. 剩余预算按优先级分配给历史消息：history_full > history_compressed > history_summary
3. 工具结果预算独立计算（属于当前请求内，非历史）

如果实际历史消息的 token 数低于预算，不做任何压缩。预算是上限而非配额。

## 3. TokenCounter

TokenCounter 提供 token 计数能力。

### 3.1 计数粒度

- 单条消息：统计 role + content 的 token 总数
- 消息列表：统计列表中所有消息的 token 总和
- 文本片段：统计任意字符串的 token 数

### 3.2 tokenizer 来源

优先使用 LLM 实例暴露的 tokenizer。如果 LLM 未暴露 tokenizer（某些 Provider 适配器的限制），回退到 tiktoken 的 cl100k_base 编码。

### 3.3 缓存

对相同文本的重复计数做缓存（LRU），避免在消息链构建过程中对同一条历史消息反复 tokenize。

## 4. Compressor

Compressor 实现三种压缩操作，按侵入性从低到高排列。

### 4.1 截断

将文本裁剪到指定 token 数。在 token 边界处截断，追加省略标记。这是最轻量的压缩方式，不调用 LLM，信息丢失可预测。

用途：工具结果压缩、Side 轨道注入 Main 历史时的截断。

### 4.2 首段提取

保留 assistant 回复的第一段（到第一个换行符或前 200 字符），丢弃后续内容。用于压缩层——assistant 的第一段通常包含核心回答，后续段落是补充说明。

用途：压缩层的 assistant 消息处理。

### 4.3 摘要生成

调用 LLM 将多条消息压缩为一段摘要文本。需要一个 summarize prompt 指导 LLM 保留哪些信息（关键事实、用户偏好、决策结论）。

用途：摘要层。异步执行，结果缓存在 SessionMemory 中供后续请求使用。

## 5. 分层压缩模型

### 5.1 三层结构

消息历史按时间从近到远分为三层：

```
[摘要层]   最早的消息 --> 一段摘要文本（异步 LLM 生成）
[压缩层]   较早的消息 --> user 原文 + assistant 首段
[完整层]   最近的消息 --> 完整保留
```

### 5.2 层级分配

层级的划分基于轮次数而非 token 数：

| 层级 | 范围 | 参考默认值 |
|------|------|-----------|
| 完整层 | 最近 N 轮 | N = 5（最近 10 条消息） |
| 压缩层 | 倒数 N+1 到 N+M 轮 | M = 10（再往前 20 条消息） |
| 摘要层 | 倒数 N+M+1 轮及更早 | 全部压缩为一段摘要 |

当总历史不超过 N 轮时，不触发任何压缩。超过 N 轮但不超过 N+M 轮时，只有压缩层，没有摘要层。

### 5.3 工具结果压缩

同一请求内的工具结果分层处理：

| 轮次 | 处理方式 |
|------|---------|
| 最后一轮工具调用 | 保留完整 content |
| 更早的工具调用 | content 截断到预算上限（如每轮 300 tokens） |

这是在 ContextBuilder 构建消息链时实时执行的（不是异步的），因为工具结果属于当前请求内的消息，不涉及跨请求的历史。

## 6. 生命周期

### 6.1 SessionMemory

与 Session 绑定。Session 开始时创建（或从持久化消息恢复），Session 存续期间在内存中维护，Session 结束时丢弃。

### 6.2 ContextBuilder

每次消息链构建时使用，无跨请求状态。它读取 SessionMemory 的当前快照，计算并返回消息链，不修改 SessionMemory 的内容。

### 6.3 摘要缓存

摘要层的生成结果缓存在 SessionMemory 中（作为一个特殊的摘要字段）。当新消息进入摘要层的范围时，标记摘要为"过期"，下一次请求结束后异步重新生成。
