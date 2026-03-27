# 中层记忆系统 (Context Compaction) -- 数据模型

本文档描述中层记忆系统引入的核心概念和数据模型变更，统一后续文档使用的术语。

所有概念均服务于 `01-goals-duty.md` 中的职责，并映射到 `02-architecture.md` 中的组件结构。

---

## 一、Core Concepts（核心概念）

### 1. Compaction（压缩）

将会话中 boundary 之后的全部消息（包括上一次的 summary）输入 LLM，生成一段新的精炼摘要的过程。每次压缩产生一条 summary 消息，并将 boundary 前移到该 summary。

### 2. Compaction Boundary（压缩边界）

一个指针，指向最近一次压缩产生的 summary 消息的 ID。boundary 的语义是：该 ID 及之前的所有消息已被当前 summary 覆盖，不再进入模型可见的消息列表。

### 3. Summary Message（摘要消息）

压缩产生的消息，role 为 assistant，message_type 为 SUMMARY。它是 LLM 以第一人称（AI 视角）对历史对话的总结。同一时刻模型只看到最近一次 boundary 之后的链（含一条 summary）。

### 4. Compaction Threshold（压缩阈值）

触发压缩的 token 用量阈值，定义为 `total * 95%`。当 boundary 之后的消息总 token 数达到此阈值时触发压缩。

---

## 二、Entity / Value Object 变更

### 1. MessageType（新增值对象）

用于区分消息的类型，位于 `domain/value_objects/mode_type.py`。

- **NORMAL**：普通的 user / assistant 对话消息
- **SUMMARY**：压缩产生的摘要消息，role 固定为 assistant

该区分使持久化层和加载逻辑能够识别 summary 消息，避免将其与普通对话消息混淆。

### 2. Message 实体变更

在现有 Message 实体上新增 `message_type` 字段：

- 默认值为 `MessageType.NORMAL`
- 压缩产生的消息设为 `MessageType.SUMMARY`
- 现有所有消息自动视为 NORMAL（向后兼容）

不引入 TOOL 类型——工具调用消息仅存在于 AgentLoop 的单次执行内存中，不持久化到数据库。

### 3. Session 实体变更

新增字段：
- `compaction_boundary_id: Optional[int]`：最近一次压缩产生的 summary 消息的 message_id。值为 None 表示该会话从未执行过压缩。

移除字段：
- `context_summary: Optional[str]`：不再使用，summary 以独立消息形式持久化
- `needs_compression` 属性：压缩判定改为基于 token 计数，不再依赖轮数
- `COMPRESSION_THRESHOLD_ROUNDS` 常量：不再使用

保留字段：
- `message_count`：用于其他统计场景，不再用于压缩判定

### 4. StoredMessage 变更

在 `SessionMemory` 使用的 `StoredMessage` 数据类上新增 `message_type` 字段：

- 默认值为 `"normal"`
- 压缩 summary 标记为 `"summary"`

此字段使 SessionMemory 中的消息携带类型信息，但 SessionMemory 本身不基于此字段做任何逻辑分支——它只负责持有消息列表。

---

## 三、Key Data Fields（关键数据字段）

### ContextBudget 变更

新增和调整的字段（以 200k 窗口为参考值）：

| 字段 | 含义 | 参考值 |
|------|------|--------|
| total | 模型上下文窗口大小 | 200,000 |
| system_prompt | system prompt 预算 | 2,000 |
| summary | summary 消息的预算上限 | 6,000 |
| history | boundary 后原始消息的预算 | ~170,000 |
| current_message | 当前用户输入预算 | 4,000 |
| tool_results | AgentLoop 内工具返回预算 | 8,000 |
| output_reserved | 模型输出预留 | 8,000 |
| main_injection | side-track 注入 main 上下文预算 | 2,000 |

新增计算属性：
- `compaction_threshold`：`int(total * 0.95)`，即 190,000

ContextBudget 不再在 SessionManager 中硬编码，应从配置层读取，支持不同 provider / 模型的窗口差异。

---

## 四、Lifecycle & Ownership（生命周期与归属）

### Summary 消息的生命周期

1. **创建**：由 CompactionService 在压缩流程中创建，通过 MessageRepository 持久化
2. **使用**：由 SessionManager 在 `_reload_memory()` 中作为 boundary 后的第一条消息加载到 SessionMemory
3. **替代**：下次压缩时，新的 summary 覆盖旧 summary 的"可见"地位（boundary 前移），但旧 summary 仍保留在数据库中
4. **不删除**：旧 summary 不被物理删除，可用于审计和回溯

### Compaction Boundary 的生命周期

1. **初始状态**：Session 创建时 `compaction_boundary_id = None`
2. **首次压缩**：设置为第一个 summary 消息的 message_id
3. **后续压缩**：更新为最新 summary 消息的 message_id
4. **归属**：由 CompactionService 负责更新，通过 SessionRepository 持久化
