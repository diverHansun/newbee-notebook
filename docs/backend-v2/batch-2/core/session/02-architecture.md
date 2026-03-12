# Session 模块：架构设计

## 1. 架构总览

Session 模块的核心是重构后的 SessionManager。它从当前的"全能管理者"精简为"编排协调者"，将具体的上下文管理和执行逻辑委托给 context 和 engine 模块。

```
SessionManager
    |
    +-- SessionMemory (context 模块)    上下文读写
    +-- ContextBuilder (context 模块)   消息链构建
    +-- ModeConfigFactory (engine 模块) 模式配置
    +-- AgentLoop (engine 模块)         执行
    +-- AsyncLock                       并发控制
```

### 1.1 对比当前实现

| 维度 | 当前 SessionManager | 重构后 SessionManager |
|------|--------------------|----------------------|
| 内存管理 | 手动管理两个 ChatMemoryBuffer，手动 put/get | 委托 context 模块 |
| 模式分发 | 通过 ModeSelector 创建和缓存 4 种 Mode | 通过 ModeConfigFactory 构建配置，调用 AgentLoop |
| Source 收集 | 从 ModeSelector 获取 last_sources | 从 AgentLoop 的 StreamEvent 中提取 |
| EC 上下文注入 | 手动构建 ec_context_summary，手动合并到 context dict | context 模块的双轨可见性规则自动处理 |
| 并发控制 | 无 | 会话级 AsyncLock |

## 2. 设计模式与理由

### 2.1 编排者模式（而非全能者模式）

SessionManager 不实现任何具体逻辑，只协调模块间的调用顺序。每个步骤的具体实现委托给专门的模块。这使得 SessionManager 的代码量从当前的约 270 行精简到预计 150 行以内，且每行都是编排逻辑而非实现细节。

### 2.2 会话级锁（而非全局锁或无锁）

并发控制的粒度是 session_id 级别。不同 Session 的请求可以并行，同一 Session 的请求串行。

理由：
- 全局锁太粗粒度，不同用户的请求不应互相阻塞。
- 无锁的风险：同一 Session 的两个并发请求可能同时读取相同的历史，各自执行后写入不同的结果，导致消息乱序。
- 会话级锁精确匹配风险范围：SessionMemory 是 per-session 的，只有同一 session 的并发写入才会冲突。

实现方式：维护一个 `Dict[str, asyncio.Lock]` 映射，按 session_id 获取或创建锁。Session 结束时清理对应的锁。

### 2.3 持久化通过 Application Service（而非直接操作 Repository）

SessionManager 属于 core 层，不应直接依赖 infrastructure 层的 Repository 实现。通过 Application Service（ChatService）间接操作，保持层级隔离。

当前实现中 SessionManager 已经通过 Repository 接口操作（依赖倒置），这一点可以保留。关键变化是 SessionManager 不再负责 Source 验证、Reference 创建等业务逻辑——这些仍由 ChatService 处理。

## 3. 模块结构与文件布局

```
core/session/
    __init__.py
    session_manager.py      SessionManager 编排协调
    lock_manager.py         会话级 AsyncLock 管理
```

### 3.1 文件职责

**session_manager.py** -- 编排核心

SessionManager 类。构造时接收 LLM、SessionMemory、ContextBuilder、以及用于持久化的回调接口。核心方法是 `chat_stream()` 和 `chat()`，编排完整的交互流程。

**lock_manager.py** -- 并发控制

SessionLockManager 类。维护 session_id 到 AsyncLock 的映射。提供 `acquire(session_id)` 上下文管理器，自动获取和释放锁。

## 4. 架构约束与权衡

### 4.1 SessionManager 的实例生命周期

SessionManager 与 Session 一一对应。Application Service 为每个活跃 Session 维护一个 SessionManager 实例。这与当前实现一致。

### 4.2 多实例间的 SessionMemory 一致性

同一 Session 不应有多个 SessionManager 实例（否则各自持有独立的 SessionMemory 副本）。Application Service 层需要确保 SessionManager 的缓存和复用逻辑正确——同一 session_id 始终映射到同一个 SessionManager 实例。

### 4.3 持久化失败的处理

如果 AgentLoop 执行成功但消息持久化失败：
- SessionMemory 中已写入新消息（内存状态已更新）。
- 数据库中缺少这些消息（持久化状态未更新）。
- 下次恢复 Session 时，从数据库加载的历史不包含这些消息。

缓解：持久化失败时记录错误日志，不回滚 SessionMemory（用户已经看到了回答）。下次请求时，SessionMemory 中仍有这些消息，不影响当前会话的连续性。只有在 Session 完全重建（如服务重启）时才会丢失这些消息。
