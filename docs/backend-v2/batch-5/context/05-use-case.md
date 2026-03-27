# 中层记忆系统 (Context Compaction) -- 用例

本文档描述中层记忆系统的关键业务动作、执行编排与责任边界。

用例均追溯到 `01-goals-duty.md` 中的职责，执行步骤的责任归属与 `02-architecture.md` 中的组件划分一致。

---

## 一、Use Case Overview（用例概览）

本模块包含以下关键业务动作：

| 用例 | 对应职责 | 触发条件 |
|------|----------|----------|
| 评估是否需要压缩 | token 用量评估 | 每次用户请求到来时 |
| 执行首次压缩 | 历史消息压缩 + summary 持久化 | 会话从未压缩，token 用量达到阈值 |
| 执行滚动压缩 | 历史消息压缩 + 边界管理 | 已有 summary，token 用量再次达到阈值 |

---

## 二、Main Flow Description（主流程描述）

### 用例 1：评估是否需要压缩

**触发**：SessionManager 在构建上下文之前调用 CompactionService。

1. CompactionService 接收 Session 实体和 track_modes
2. 从数据库加载 boundary 之后的全部 main-track 消息
3. 将消息转换为 dict 格式，调用 TokenCounter 计算总 token 数
4. 与 ContextBudget.compaction_threshold（total * 95%）比较
5. 未达阈值：返回 False，流程结束

**责任归属**：步骤 1 由 SessionManager 发起，步骤 2~5 由 CompactionService 负责。

### 用例 2：执行首次压缩

**触发**：用例 1 判定需要压缩，且 session.compaction_boundary_id 为 None。

1. CompactionService 从数据库加载该 session 的全部 main-track 消息
2. 将消息序列格式化为压缩 prompt（system 指令 + user/assistant 交替文本）
3. 调用 LLMClient 生成 summary
4. 使用 TokenCounter 校验 summary 长度，超出上限则截断
5. 通过 MessageRepository 创建 SUMMARY 类型的 assistant 消息
6. 通过 SessionRepository 将 compaction_boundary_id 更新为该 summary 的 message_id
7. 返回 True

**责任归属**：全部步骤由 CompactionService 负责。LLMClient 和 Repository 是被调用的外部能力。

### 用例 3：执行滚动压缩

**触发**：用例 1 判定需要压缩，且 session.compaction_boundary_id 不为 None。

1. CompactionService 从数据库加载 boundary 之后的消息（含上一次 summary + 后续原始消息）
2. 构造压缩 prompt：上一次 summary 和中间全部对话作为输入，要求 LLM 重新总结
3. 调用 LLMClient 生成新的 summary
4. 使用 TokenCounter 校验长度，超出上限则截断
5. 通过 MessageRepository 创建新的 SUMMARY 消息
6. 通过 SessionRepository 将 compaction_boundary_id 更新为新 summary 的 message_id
7. 返回 True

**与首次压缩的区别**：步骤 1 的加载范围不同（全量 vs boundary 之后），步骤 2 的输入包含旧 summary。压缩完成后，旧 summary 仍保留在数据库中，但 boundary 前移使其不再进入模型可见范围。

---

## 三、Responsibility Boundaries（责任边界）

### CompactionService 负责

- 加载消息、计算 token、判定阈值
- 构造压缩 prompt 和调用 LLM
- 创建 SUMMARY 消息和更新 boundary 指针

### SessionManager 负责

- 在请求处理流程中决定何时调用 CompactionService
- 压缩完成后重新加载 SessionMemory
- 将更新后的 memory 传递给 ContextBuilder

### 外部模块负责

- MessageRepository / SessionRepository：数据持久化，不涉及业务逻辑
- LLMClient：生成 summary 文本，不感知压缩上下文
- TokenCounter：token 计数，纯计算，无副作用

### 不属于本模块的职责

- 上下文消息列表的最终组装（ContextBuilder）
- 消息的创建和持久化（ChatService 在正常对话流程中负责）
- 配置 ContextBudget 的具体数值（配置层）

---

## 四、Failure & Decision Points（失败点与决策点）

### 1. LLM 调用失败

场景：压缩时调用 LLM 生成 summary 失败（网络异常、API 限流、模型不可用）。

预期行为：
- CompactionService 不创建 SUMMARY 消息，不更新 boundary
- 返回 False（等同于未触发压缩）
- 本次请求继续使用未压缩的完整消息列表处理
- 下次请求到来时会再次检查并尝试压缩

设计决策：不做重试。压缩失败不阻塞用户请求，降级为使用完整消息（此时 ContextBuilder 的 fit_messages 会截断最旧消息以适应预算）。

### 2. Summary 超出长度限制

场景：LLM 生成的 summary 超出 summary_max_tokens 上限。

预期行为：
- 使用 Compressor 按 token 截断 summary 到上限
- 截断后的 summary 仍然持久化和使用

设计决策：截断优于拒绝。即使被截断，部分 summary 仍优于没有 summary。

### 3. 压缩过程中的并发请求

场景：压缩正在执行时，同一 session 的另一个请求到来。

预期行为：
- SessionManager 已有 SessionLockManager 提供 session 级别的异步锁
- 后续请求会等待锁释放后再执行，此时压缩已完成
- 不会出现两个请求同时为同一 session 执行压缩的情况

### 4. 上下文窗口不足以容纳压缩 prompt

场景：极端情况下，需要压缩的消息总量超出 LLM 的上下文窗口。

预期行为：
- 由于阈值设为 95%，而压缩 prompt 的 system 指令很短（约 200 tokens），正常情况下不会超限
- 如果确实超限（异常场景），LLM 调用会失败，回退到失败点 1 的处理逻辑
