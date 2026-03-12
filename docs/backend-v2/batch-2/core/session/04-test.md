# Session 模块：验证策略

## 1. 测试范围

| 测试对象 | 覆盖 |
|---------|------|
| SessionManager 编排流程 | 是 |
| 会话恢复 | 是 |
| 并发控制 | 是 |
| 取消机制 | 是 |
| 模式到轨道的映射 | 是 |

| 排除对象 | 理由 |
|---------|------|
| SessionMemory 内部逻辑 | 属于 context 模块 |
| AgentLoop 执行逻辑 | 属于 engine 模块 |
| 消息持久化 | 属于 Application Service / Repository 层 |

## 2. 关键场景

### 2.1 编排流程

**场景：Agent 模式完整编排**

调用 chat_stream(mode=AGENT, message="...")。验证：
- ModeConfigFactory.build() 被调用且参数正确。
- ContextBuilder.build(track="main") 被调用。
- AgentLoop.stream() 被调用。
- 执行完成后 SessionMemory.append(track="main", ...) 被调用。
- StreamEvent 被正确透传。

**场景：Explain 模式编排**

调用 chat_stream(mode=EXPLAIN, selected_text="...")。验证：
- ModeConfigFactory.build() 收到 selected_text 参数。
- ContextBuilder.build(track="side", inject_main=True) 被调用。
- 执行完成后 SessionMemory.append(track="side", ...) 被调用。

**场景：模式到轨道映射**

对四种模式分别发送请求，验证 Agent/Ask 写入 "main"，Explain/Conclude 写入 "side"。

### 2.2 会话恢复

**场景：从持久化消息恢复**

调用 restore() 传入 CA 和 EC 消息列表。验证 SessionMemory.load_from_messages() 被调用且参数分类正确。

**场景：恢复后立即交互**

restore() 后调用 chat_stream()。验证 ContextBuilder.build() 返回的消息链包含恢复的历史。

### 2.3 并发控制

**场景：同一 Session 的并发请求串行化**

同时发起两个 chat_stream() 调用（相同 session_id）。验证第二个请求在第一个完成后才开始执行（通过执行时间或调用顺序判断）。

**场景：不同 Session 的请求并行**

同时发起两个 chat_stream() 调用（不同 session_id）。验证两个请求并行执行。

### 2.4 取消

**场景：取消活跃请求**

chat_stream() 执行过程中调用 cancel_active_request()。验证 AgentLoop.cancel() 被调用，StreamEvent 序列包含 DoneEvent。

## 3. 验证方法

单元测试使用 pytest + pytest-asyncio。Mock context 模块（SessionMemory、ContextBuilder）和 engine 模块（ModeConfigFactory、AgentLoop）。验证 SessionManager 的编排调用顺序和参数传递。

测试文件：
```
tests/unit/core/session/
    test_session_manager.py     编排流程、恢复、取消
    test_lock_manager.py        并发控制
```
