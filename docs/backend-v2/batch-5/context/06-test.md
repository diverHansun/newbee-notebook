# 中层记忆系统 (Context Compaction) -- 测试策略

本文档描述中层记忆系统的测试范围、关键场景与验证策略。

测试围绕 `01-goals-duty.md` 中的职责展开，覆盖 `04-dfd-interface.md` 中的关键数据流和 `05-use-case.md` 中的失败点。

---

## 一、Test Scope（测试范围）

### 覆盖范围

- TokenCounter 基于 tiktoken 的 token 计数准确性
- Compressor 基于 token 的截断行为
- ContextBudget 的 compaction_threshold 计算
- CompactionService 的压缩判定逻辑（阈值比较）
- CompactionService 的首次压缩流程
- CompactionService 的滚动压缩流程（含旧 summary 的处理）
- CompactionService 的 summary 长度校验与截断
- CompactionService 的失败降级行为
- SessionManager 中前置拦截的集成行为
- MessageRepository.list_after_boundary 的查询正确性

### 不在测试范围内

- LLM 生成 summary 的内容质量（取决于模型能力，非本模块可控）
- ContextBuilder 的消息组装逻辑（该组件未改动核心逻辑，由其既有测试覆盖）
- AgentLoop 的执行行为（与压缩无直接交互）
- side-track（EXPLAIN / CONCLUDE）的消息管理

---

## 二、Critical Scenarios（关键场景）

### TokenCounter 相关

1. **中英文混合文本的 token 计数**：给定一段中英文混合内容，计数结果应与 tiktoken 直接编码一致。
2. **空内容处理**：空字符串、None、纯空白字符串的 token 数均为 0。
3. **消息列表计数包含 overhead**：每条消息应包含约 4 tokens 的固定开销。

### Compressor 相关

4. **按 token 截断保持文本完整性**：截断后的文本应能被正常解码，不产生乱码。
5. **未超限文本不被截断**：token 数未超出限制的文本原样返回。

### CompactionService 判定逻辑

6. **未达阈值不触发压缩**：消息 token 总量低于 compaction_threshold 时，返回 False，不调用 LLM，不写入数据库。
7. **达到阈值触发压缩**：消息 token 总量达到 compaction_threshold 时，执行压缩流程。
8. **空会话不触发压缩**：session 无消息时直接返回 False。

### 首次压缩流程

9. **boundary 为 None 时加载全部消息**：CompactionService 从数据库加载该 session 的全部 main-track 消息用于压缩。
10. **创建 SUMMARY 消息并更新 boundary**：压缩完成后，数据库中存在一条 message_type=SUMMARY 的 assistant 消息，session.compaction_boundary_id 指向该消息的 ID。

### 滚动压缩流程

11. **boundary 不为 None 时只加载 boundary 之后的消息**：加载结果包含上一次 summary 和后续原始消息。
12. **旧 summary 保留在数据库中**：压缩后旧 summary 不被删除，但 boundary 前移。
13. **多次压缩后模型只看到最新链**：经过 N 次压缩后，list_after_boundary 返回的消息列表只包含最新的 summary 和其后的原始消息。

### Summary 长度控制

14. **超出上限的 summary 被截断**：当 LLM 返回的 summary 超过 summary_max_tokens 时，持久化的 summary 长度不超过上限。
15. **未超限的 summary 原样保留**：正常长度的 summary 不被截断。

### 失败降级

16. **LLM 调用失败时不创建 summary**：返回 False，session.compaction_boundary_id 不变。
17. **LLM 调用失败不阻塞用户请求**：SessionManager 在 CompactionService 返回 False 后继续正常处理。

---

## 三、Integration Points（集成点测试）

### 1. CompactionService 与 SessionManager 的集成

验证重点：
- SessionManager 在 chat_stream 流程中正确调用 compact_if_needed
- 压缩完成后 SessionManager 重新加载 memory
- 重新加载后 SessionMemory 中只包含 boundary 之后的消息
- 压缩未触发时，SessionManager 的行为与之前完全一致

### 2. CompactionService 与 MessageRepository 的集成

验证重点：
- list_after_boundary 在 boundary 为 None 时返回全部消息
- list_after_boundary 在 boundary 不为 None 时返回正确范围
- SUMMARY 消息能被正确创建和查询
- SUMMARY 消息的 message_type 字段在数据库中正确持久化

### 3. CompactionService 与 LLMClient 的集成

验证重点：
- 压缩 prompt 格式正确（system 指令 + 消息序列）
- 不传递 tools 和 tool_choice（压缩不使用工具）
- LLM 返回内容被正确提取为 summary 文本

---

## 四、Verification Strategy（验证策略）

### 单元测试

- **TokenCounter**：直接测试，不 mock。tiktoken 是确定性的本地库，无外部依赖。
- **Compressor**：直接测试，依赖 TokenCounter 实例。
- **ContextBudget**：直接测试 compaction_threshold 计算。
- **CompactionService 判定逻辑**：mock MessageRepository（返回预设消息列表），mock LLMClient（返回预设 summary），验证判定和流程编排是否正确。

### 集成测试

- **CompactionService 完整流程**：使用内存实现的 MessageRepository 和 SessionRepository，mock LLMClient，验证从判定到持久化的完整流程。
- **SessionManager + CompactionService**：验证前置拦截的集成行为，确保压缩对下游流程透明。

### 不使用真实 LLM 的理由

summary 内容质量依赖模型能力，不可在自动化测试中稳定验证。测试中 mock LLMClient 返回固定内容，关注的是 CompactionService 的编排逻辑是否正确，而非 summary 的语义质量。
