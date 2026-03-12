# Session 模块：设计目标与职责边界

## 1. 设计目标

### 1.1 清晰的编排职责

Session 模块是交互请求的编排者。它协调 context（上下文）、engine（执行）、tools（工具构建）三个模块完成一次完整的交互：获取历史 -> 构建配置 -> 执行 AgentLoop -> 写回历史 -> 持久化消息。编排逻辑集中在一处，而非分散在各模块中。

### 1.2 会话状态一致性

确保会话的内存状态（SessionMemory）和持久化状态（数据库中的 Message 记录）保持一致。新消息先写入 SessionMemory，再持久化到数据库。异常情况下（持久化失败），内存状态可以回滚或在下次加载时从数据库重建。

### 1.3 并发安全

同一 Session 同一时刻只有一个请求在执行。通过会话级锁防止并发写入导致的消息乱序或 SessionMemory 状态损坏。

## 2. 职责

### 2.1 会话生命周期

管理会话的创建、恢复和结束。

- 创建：分配 session_id，初始化 SessionMemory。
- 恢复：根据 session_id 从数据库加载历史消息，调用 context 模块的 SessionMemory.load_from_messages() 重建内存状态。
- 结束：清空 SessionMemory，释放资源。

### 2.2 请求编排

协调一次完整的交互请求：

1. 从请求中提取 mode、message/selected_text、rag_config 等参数。
2. 调用 ModeConfigFactory.build() 获取 ModeConfig。
3. 调用 ContextBuilder.build() 获取消息链。
4. 创建 AgentLoop 实例，执行 stream() 或 run()。
5. 将新消息（user + assistant）写入 SessionMemory。
6. 协调 Application Service 层持久化消息到数据库。
7. 触发异步摘要（如果需要）。

### 2.3 消息持久化协调

Session 模块不直接操作数据库（不持有 Repository）。它通过 Application Service 层（ChatService）完成持久化。Session 模块的职责是确定"哪些消息需要持久化"以及"何时触发持久化"。

### 2.4 并发控制

维护会话级别的异步锁。同一 session_id 的并发请求被串行化——第二个请求等待第一个完成后再执行。这避免了 SessionMemory 的竞争写入。

### 2.5 活跃请求管理

跟踪当前正在执行的 AgentLoop 实例，支持取消操作。当收到取消信号时，找到对应的 AgentLoop 并调用 cancel()。

## 3. 非职责

### 3.1 上下文管理

Session 模块不管理双轨内存模型的内部逻辑、不做 token 预算分配、不执行压缩。这些是 context 模块的职责。Session 模块只调用 context 模块的接口。

### 3.2 执行逻辑

Session 模块不实现工具调用循环、不产出流式事件、不与 LLM 直接交互。这些是 engine 模块的职责。

### 3.3 工具构建

Session 模块不构建工具列表。ModeConfigFactory（属于 engine 模块）负责根据参数构建工具列表。

### 3.4 数据库操作

Session 模块不直接持有 Repository，不执行 SQL。它通过 Application Service 层间接操作。这保持了 core 层与 infrastructure 层的隔离。

### 3.5 HTTP 协议

Session 模块不处理 HTTP 请求/响应。API Router 层负责协议处理，调用 Session 模块的接口。
