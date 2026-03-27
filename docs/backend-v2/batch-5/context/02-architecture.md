# 中层记忆系统 (Context Compaction) -- 架构

本文档描述中层记忆系统的内部结构、组件职责划分与设计取舍。

所有架构决策均服务于 `01-goals-duty.md` 中确认的设计目标与职责边界。

---

## 一、Architecture Overview（总体架构）

中层记忆系统由以下组件构成，各组件通过明确的依赖关系协作：

### 1. CompactionService（压缩服务）

核心编排组件，负责完整的压缩判定与执行流程。

职责：
- 从数据库加载 boundary 之后的消息
- 计算 token 总量并与阈值比较
- 构造压缩 prompt，调用 LLM 生成 summary
- 持久化 summary 消息并更新 Session 的 boundary 指针

依赖：LLMClient、MessageRepository、SessionRepository、TokenCounter、ContextBudget

### 2. TokenCounter（token 计数器）

基础设施组件，提供准确的 token 计数能力。

职责：
- 基于 tiktoken（cl100k_base 编码）计算文本和消息列表的 token 数
- 包含 per-message overhead 计算，反映实际 API 用量

被依赖方：CompactionService、Compressor、ContextBuilder

### 3. Compressor（截断器）

基础设施组件，提供基于 token 的文本截断和消息拟合能力。

职责：
- 按 token 数截断文本（替代原有的按空格截断）
- 在给定预算内裁剪消息列表（丢弃最旧消息）

被依赖方：ContextBuilder、CompactionService（用于截断超长 summary）

### 4. ContextBudget（预算配置）

值对象，定义上下文窗口的各项预算分配。

职责：
- 承载 total、system_prompt、summary、history 等预算字段
- 提供 compaction_threshold 计算属性（total * 95%）

### 5. SessionMemory / ContextBuilder（既有组件，无需改动核心逻辑）

SessionMemory 持有 boundary 后的消息列表（由 SessionManager 在加载阶段完成过滤），ContextBuilder 基于 SessionMemory 中的内容构建最终消息列表。这两个组件不感知压缩的存在。

### 组件协作关系

```
SessionManager
  |
  |-- (1) 调用 CompactionService.compact_if_needed()
  |       |-- 读取 MessageRepository (boundary 之后的消息)
  |       |-- 使用 TokenCounter 计算 token 总量
  |       |-- 比较 ContextBudget.compaction_threshold
  |       |-- 如需压缩: 调用 LLMClient 生成 summary
  |       |-- 写入 MessageRepository (SUMMARY 消息)
  |       |-- 更新 SessionRepository (boundary 指针)
  |
  |-- (2) 调用 _reload_memory() (加载 boundary 后的消息到 SessionMemory)
  |
  |-- (3) 调用 ContextBuilder.build() (基于 SessionMemory 组装消息列表)
  |
  |-- (4) 调用 AgentLoop.stream() (执行推理)
```

---

## 二、Design Pattern & Rationale（设计模式与理由）

### 前置拦截模式

CompactionService 在 SessionManager 的请求处理流程中作为**前置步骤**执行，而非嵌入 ContextBuilder 内部。

理由：
- 保持 ContextBuilder 的单一职责（纯组装），不引入 LLM 调用和数据库写入等副作用
- 压缩逻辑可独立测试，不依赖 ContextBuilder 的内部状态
- 压缩执行与否对后续流程透明，SessionManager 只需在压缩后重新加载 memory

### 未采用事件驱动模式

压缩本质上是一个同步前置步骤（用户需要等待压缩完成后才能得到回复），引入事件系统会增加异步协调的复杂度，收益有限。

### 未采用异步后台压缩

异步压缩（响应完成后再压缩）会导致下次请求到来时 boundary 尚未更新，仍需在请求处理中检查和等待，反而增加了状态管理复杂度。同步前置方式虽增加单次请求延迟，但状态一致性更好。

---

## 三、Module Structure & File Layout（模块结构与文件组织）

```
core/context/
  __init__.py              # 模块导出
  token_counter.py         # [改造] 接入 tiktoken，替代空格分词
  compressor.py            # [改造] 截断逻辑适配 tiktoken
  budget.py                # [改造] 新增 summary 字段、compaction_threshold 属性
  session_memory.py         # [改造] StoredMessage 新增 message_type 字段
  context_builder.py        # [不变] 保持纯组装职责
  compaction_service.py     # [新增] 压缩判定与执行服务
  compaction_prompt.py      # [新增] 压缩 prompt 模板

domain/entities/
  session.py               # [改造] 新增 compaction_boundary_id，移除 context_summary 等遗留字段
  message.py               # [改造] 新增 message_type 字段

domain/value_objects/
  mode_type.py             # [改造] 新增 MessageType 枚举

domain/repositories/
  message_repository.py    # [改造] 新增 list_after_boundary 方法

core/session/
  session_manager.py       # [改造] 注入 CompactionService，在 chat_stream 前置调用
```

稳定对外接口：ContextBuilder.build()、SessionMemory 的公共方法。
内部实现：CompactionService 的压缩逻辑、压缩 prompt 模板。

---

## 四、Architectural Constraints & Trade-offs（约束与权衡）

### 1. 接受压缩带来的单次请求延迟

触发压缩时，需要额外一次 LLM 调用（约 2~5 秒），用户会感知到该次请求的响应变慢。这是为语义一致性付出的代价——使用同一 LLM 做总结，确保 summary 的质量与风格与正常对话一致。

被放弃的方案：使用轻量模型（如 mini）做总结，可降低延迟和成本，但可能产生语义偏差。

### 2. tiktoken 作为通用 tokenizer

使用 cl100k_base 编码作为所有 provider 的统一 tokenizer，误差在 5% 以内。配合 95% 触发阈值，有约 5% 的安全余量，足以覆盖 tokenizer 差异。

被放弃的方案：为每个 provider 适配专用 tokenizer，实现复杂度高，收益有限。

### 3. Summary 长度硬约束

summary 输出控制在 4000~6000 tokens。过短会丢失关键信息，过长会在多次压缩后挤占上下文空间。该范围在 200k 窗口下仅占约 3%，对后续对话的影响可接受。

### 4. 仅压缩 main-track

side-track（EXPLAIN / CONCLUDE）有 12 条消息硬限制，本身不会触及上下文窗口瓶颈，不需要也不应该被压缩。这简化了压缩逻辑，避免跨 track 的边界管理。
