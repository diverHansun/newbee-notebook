# 中层记忆系统 (Context Compaction) -- 数据流与接口

本文档描述中层记忆系统与外部模块的数据流动关系，以及对外暴露和依赖的接口。

数据流先于接口描述。接口是数据流的承载形式，而非设计起点。

---

## 一、Context & Scope（上下文与范围）

本模块与以下外部模块存在交互：

| 外部模块 | 交互方向 | 交互内容 |
|----------|----------|----------|
| SessionManager | 被调用方 | SessionManager 在请求处理前调用本模块进行压缩检查 |
| MessageRepository | 依赖 | 读取 boundary 之后的消息，写入 summary 消息 |
| SessionRepository | 依赖 | 读取和更新 Session 的 compaction_boundary_id |
| LLMClient | 依赖 | 调用 LLM 生成 summary |
| TokenCounter | 依赖 | 计算消息的 token 总量 |
| ContextBudget | 依赖 | 获取 compaction_threshold 阈值 |

本文档仅讨论上述交互范围。ContextBuilder、AgentLoop 等下游组件不与本模块直接交互。

---

## 二、Data Flow Description（数据流描述）

### 主数据流：压缩检查与执行

```
(1) SessionManager 发起压缩检查
       |
       v
(2) CompactionService 从 MessageRepository 加载消息
    - 如果 session.compaction_boundary_id 为 None: 加载该 session 的全部 main-track 消息
    - 否则: 加载 boundary_id 之后的消息（含 boundary 指向的 summary 消息本身）
       |
       v
(3) CompactionService 使用 TokenCounter 计算消息总 token 数
       |
       v
(4) 与 ContextBudget.compaction_threshold 比较
    - 未达阈值: 流程结束，返回 False，SessionManager 继续正常处理
    - 达到阈值: 进入压缩流程
       |
       v
(5) CompactionService 构造压缩 prompt
    - system message: 压缩指令模板（要求保留关键决策、事实信息，控制输出长度）
    - 消息序列: 将步骤 (2) 加载的消息格式化为 user/assistant 交替文本
       |
       v
(6) 调用 LLMClient.chat() 生成 summary 文本
       |
       v
(7) 使用 TokenCounter 验证 summary 长度
    - 如超出 summary_max_tokens 上限: 使用 Compressor 截断
       |
       v
(8) 持久化
    - 通过 MessageRepository 创建 SUMMARY 类型的 assistant 消息
    - 通过 SessionRepository 更新 session.compaction_boundary_id 为新 summary 的 message_id
       |
       v
(9) 返回 True，SessionManager 重新加载 memory 后继续正常处理
```

### 辅助数据流：memory 加载（SessionManager 侧）

压缩完成后，SessionManager 重新加载 memory：

```
(1) SessionManager 调用 MessageRepository.list_after_boundary()
    - 传入 session.compaction_boundary_id
    - 返回 boundary 之后的消息列表（第一条为 summary，后续为原始消息）
       |
       v
(2) 消息列表加载到 SessionMemory
       |
       v
(3) ContextBuilder.build() 基于 SessionMemory 组装最终消息列表
    - 结果: [system_prompt] + [summary (assistant)] + [近期消息...] + [current_message]
```

---

## 三、Interface Definition（接口定义）

### 1. CompactionService 对外接口（由 SessionManager 调用）

**compact_if_needed**
- 输入：Session 实体、track_modes 列表（指定压缩哪些模式的消息）
- 输出：布尔值，True 表示执行了压缩，False 表示未触发
- 特性：同步阻塞（async/await），压缩完成后才返回
- 副作用：可能创建新的 SUMMARY 消息、更新 Session 的 boundary 指针

### 2. MessageRepository 新增接口（由 CompactionService 和 SessionManager 调用）

**list_after_boundary**
- 输入：session_id、boundary_message_id（可为 None）、modes（可选的模式过滤）
- 输出：Message 列表，按创建时间正序排列
- 语义：boundary_message_id 为 None 时返回该 session 的全部消息；否则返回 boundary_id 及之后（含 boundary 本身）的消息
- 特性：只读查询

### 3. SessionRepository 变更（由 CompactionService 调用）

**update_compaction_boundary**
- 输入：session_id、compaction_boundary_id
- 输出：无（或更新后的 Session）
- 语义：更新 Session 的 compaction_boundary_id 字段
- 特性：写操作

### 4. TokenCounter 接口（无变更，被 CompactionService 依赖）

**count_messages**
- 输入：消息列表（dict 格式）
- 输出：token 总数（int）
- 语义：基于 tiktoken 编码计算精确 token 数，含 per-message overhead

### 5. LLMClient 接口（无变更，被 CompactionService 依赖）

**chat**
- 输入：messages 列表、tools（None）、tool_choice（None）
- 输出：LLM 响应
- 语义：压缩场景下不使用工具，仅生成文本 summary

---

## 四、Data Ownership & Responsibility（数据归属与责任）

| 数据 | 创建者 | 更新者 | 说明 |
|------|--------|--------|------|
| SUMMARY 消息 | CompactionService | 无（创建后不修改） | 通过 MessageRepository 持久化，旧 summary 不删除 |
| compaction_boundary_id | CompactionService | CompactionService | 每次压缩时更新，通过 SessionRepository 持久化 |
| boundary 后的消息列表 | ChatService（原有流程） | 无 | CompactionService 只读取，不修改原始消息 |
| SessionMemory 中的消息 | SessionManager | SessionManager | 压缩后由 SessionManager 重新加载，CompactionService 不直接操作 SessionMemory |

关键原则：
- CompactionService 对原始消息只读不写，它只产生新的 SUMMARY 消息
- SessionMemory 的内容由 SessionManager 全权管理，CompactionService 不直接操作内存状态
- boundary 指针的更新是 CompactionService 的专属责任，其他组件不应修改该字段
