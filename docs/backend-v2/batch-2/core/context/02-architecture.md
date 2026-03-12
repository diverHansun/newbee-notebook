# Context 模块：架构设计

## 1. 架构总览

Context 模块由四个内部组件构成：

```
SessionMemory           双轨内存容器
    |
ContextBuilder          消息链组装器（消费 SessionMemory，产出 List[ChatMessage]）
    |
    +-- TokenCounter    Token 统计（基于 LLM tokenizer）
    +-- Budget          预算分配策略
    +-- Compressor      压缩执行器（截断、摘要）
```

SessionMemory 是数据容器，存储两条轨道的原始消息。ContextBuilder 是计算组件，从 SessionMemory 读取消息，根据 Budget 分配的 token 预算，通过 Compressor 执行必要的压缩，最终输出一个可直接传给 LLM 的 `List[ChatMessage]`。

### 1.1 对比当前实现

| 维度 | 当前实现 | 重构后 |
|------|---------|--------|
| 内存容器 | 两个 ChatMemoryBuffer（CA 64K tokens、EC 2K tokens） | SessionMemory 双轨模型 |
| 压缩策略 | ChatSummaryMemoryBuffer 自动摘要（token 超限时同步调 LLM） | 分层压缩（完整/压缩/摘要三层），摘要异步执行 |
| token 管理 | LlamaIndex 内部隐式处理 | 显式 token 预算分配 |
| 工具结果处理 | 无特殊处理，全部保留在消息链中 | 最近完整、较早压缩 |
| EC 上下文注入 | ec_context_summary 字符串拼接到 context dict | Side 轨道构建消息链时自动注入 Main 历史 |

## 2. 设计模式与理由

### 2.1 双轨模型（而非单一 Memory + 过滤）

**选择：** 两条独立的消息列表（Main 和 Side），各自独立管理。

**放弃：** 将所有消息放在一个列表中，通过 mode 标签过滤。

**理由：** 单一列表 + 过滤看似更简单，但带来两个问题：一是 token 预算无法按轨道独立分配（Side 轨道需要更严格的限制，因为它还要装 Main 的只读历史）；二是压缩策略不同（Main 可以做深度摘要，Side 的压缩更保守因为消息量本身较少）。独立列表让每条轨道的管理策略互不干扰。

### 2.2 分层压缩（而非全量摘要）

**选择：** 完整层 + 压缩层 + 摘要层的金字塔结构。

**放弃：** 当前的 ChatSummaryMemoryBuffer 策略（超限时将所有旧消息替换为一段摘要）。

**理由：**

全量摘要的问题：摘要是有损压缩，一旦生成就无法恢复原始信息。如果摘要遗漏了某个后续对话需要引用的细节，LLM 的回答质量会下降。

分层策略的优势：
- 完整层保留最近对话的全部细节，LLM 可以准确引用。
- 压缩层保留用户的原始问题（这是最重要的上下文线索），只压缩 assistant 的冗长回答。
- 摘要层用于很早的对话，这些内容被直接引用的概率很低，一段摘要足够提供背景。

### 2.3 异步摘要（而非同步阻塞）

**选择：** 摘要层的 LLM 调用在请求结束后异步执行。

**放弃：** 在消息链构建时同步调用 LLM 生成摘要（当前 ChatSummaryMemoryBuffer 的做法）。

**理由：** 同步摘要直接增加用户等待时间。假设摘要调用需要 2-3 秒，这 2-3 秒完全浪费在用户感知不到价值的操作上。异步执行意味着：本次请求使用截断版本（信息量略低于摘要但零延迟），下次请求时摘要已就绪。

**权衡：** 第一次触发摘要的请求使用的是截断版历史（压缩层 + 截断的旧消息）而非摘要版。这意味着该次请求的 LLM 上下文质量略低。但考虑到触发摘要说明对话已经很长（几十轮），早期对话被精确引用的概率本身就很低，这个权衡是可接受的。

### 2.4 token 预算制（而非 token 上限触发）

**选择：** 为消息链的各部分预分配 token 预算，构建时主动裁剪至预算内。

**放弃：** 设置一个总 token 上限，超出时触发压缩（被动策略）。

**理由：** 被动策略的问题是"先膨胀后压缩"——消息链先无限制增长到超限，然后一次性大量压缩，造成上下文质量的剧烈波动。预算制让每个部分始终在可控范围内，上下文质量平稳退化而非断崖式下降。

## 3. 模块结构与文件布局

```
core/context/
    __init__.py
    session_memory.py       SessionMemory 双轨容器
    context_builder.py      ContextBuilder 消息链组装
    token_counter.py        TokenCounter 统计
    budget.py               ContextBudget 预算分配
    compressor.py           Compressor 压缩策略（截断 + 摘要）
```

### 3.1 文件职责

**session_memory.py** -- 双轨容器

SessionMemory 类，内部维护两个 `List[ChatMessage]`（main_history 和 side_history）。提供按轨道读写消息的接口、Side 轨道的容量裁剪、从持久化消息列表恢复状态。纯数据管理，不做 token 计算。

**context_builder.py** -- 消息链组装

ContextBuilder 类，核心方法 `build(track, system_prompt) -> List[ChatMessage]`。从 SessionMemory 取历史，通过 TokenCounter 计算 token 数，根据 Budget 判断是否需要压缩，调用 Compressor 执行压缩，最终组装出完整的消息链。

**token_counter.py** -- Token 统计

TokenCounter 类，基于 LLM 实例的 tokenizer 提供 token 计数能力。方法包括：统计单条消息的 token 数、统计消息列表的总 token 数、判断是否超出预算。

**budget.py** -- 预算分配

ContextBudget 数据类，定义各部分的 token 预算上限。根据模型的上下文窗口大小和各部分的优先级，计算分配方案。预算可通过配置文件调整。

**compressor.py** -- 压缩策略

Compressor 类，实现三种压缩操作：截断（将消息文本裁剪到指定 token 数）、首段提取（保留 assistant 回复的第一段）、摘要生成（调用 LLM 将多条消息压缩为一段摘要文本）。前两种是同步操作，摘要生成是异步操作。

## 4. 架构约束与权衡

### 4.1 tokenizer 依赖

TokenCounter 依赖 LLM 实例的 tokenizer。不同 Provider 的 tokenizer 不同（Qwen 用自己的、OpenAI 用 tiktoken）。如果 LLM 实例没有暴露 tokenizer，回退到 tiktoken 的 cl100k_base 编码做近似估算。

**风险：** 近似估算对中文文本可能有偏差（tiktoken 的中文 token 化与 Qwen 不完全一致）。

**缓解：** 预算分配时保留足够的安全余量（如只使用模型上下文窗口的 60%），吸收估算误差。

### 4.2 摘要质量

摘要层的 LLM 调用使用与主对话相同的 LLM 实例。摘要质量取决于 LLM 的指令遵循能力和 summarize prompt 的设计。

**风险：** 摘要可能遗漏后续对话需要引用的关键信息。

**缓解：** 摘要层只用于很早的对话（已经过完整层和压缩层的缓冲）。即使摘要有遗漏，最近的对话上下文仍然完整。

### 4.3 Side 轨道注入 Main 历史的 token 开销

Explain/Conclude 的消息链中包含 Main 轨道的近期历史。如果 Main 轨道的对话很长，即使截断后也可能占用 Side 轨道大量的 token 预算。

**缓解：** ContextBuilder 为 Main 历史的注入设置独立的 token 预算上限（区别于 Main 轨道自身的预算）。当 Main 历史超出注入预算时，只保留最近的几轮。
