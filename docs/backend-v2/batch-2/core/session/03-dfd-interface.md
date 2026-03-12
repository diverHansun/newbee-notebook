# Session 模块：数据流与接口定义

## 1. 上下文与范围

Session 模块位于 Application Service 层和 core 模块之间：

- 上游：ChatService（Application Service）调用 SessionManager 执行交互。
- 下游：context 模块（SessionMemory、ContextBuilder）、engine 模块（ModeConfigFactory、AgentLoop）。

## 2. 数据流

### 2.1 会话恢复流程

用户打开已有会话时：

1. ChatService 通过 session_id 获取 SessionManager 实例（缓存中取或新建）。
2. 若新建，ChatService 从 MessageRepository 加载历史消息。
3. 按 mode 分为 CA 消息（Chat/Ask）和 EC 消息（Explain/Conclude）。
4. 调用 SessionManager.restore(ca_messages, ec_messages, context_summary)。
5. SessionManager 调用 SessionMemory.load_from_messages() 恢复双轨状态。

### 2.2 交互请求流程

一次 chat_stream 请求的完整编排：

1. ChatService 调用 SessionManager.chat_stream(mode, message, rag_config, ...)。
2. SessionManager 获取会话锁。
3. 确定轨道：Agent/Ask -> "main"，Explain/Conclude -> "side"。
4. 调用 ModeConfigFactory.build() 获取 ModeConfig。
5. 调用 ContextBuilder.build(track, system_prompt) 获取消息链。
6. 创建 AgentLoop，调用 stream(user_message, chat_history)。
7. 透传 StreamEvent 给调用方（ChatService -> API Router -> SSE）。
8. AgentLoop 执行完成后，从 DoneEvent 提取完整回答和 Source。
9. 将 user_message 和 assistant_response 构造为 ChatMessage。
10. 调用 SessionMemory.append(track, [user_msg, assistant_msg])。
11. 释放会话锁。
12. 返回元数据（response、sources）供 ChatService 持久化。

### 2.3 取消流程

1. ChatService 调用 SessionManager.cancel_active_request(session_id)。
2. SessionManager 查找活跃的 AgentLoop 实例。
3. 调用 AgentLoop.cancel()。
4. AgentLoop 在下一个检查点停止，产出 DoneEvent。
5. 正常走步骤 8-12 的收尾流程（部分结果也需要持久化）。

## 3. 接口定义

### 3.1 SessionManager

```python
class SessionManager:
    def __init__(
        self,
        llm: LLM,
        memory: SessionMemory,
        context_builder: ContextBuilder,
    ) -> None: ...

    async def restore(
        self,
        main_messages: List[MessageEntity],
        side_messages: List[MessageEntity],
        context_summary: Optional[str] = None,
    ) -> None:
        """从持久化消息恢复会话状态。"""

    async def chat_stream(
        self,
        mode: ModeType,
        message: Optional[str] = None,
        selected_text: Optional[str] = None,
        rag_config: Optional[RAGConfig] = None,
        allowed_document_ids: Optional[List[str]] = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """流式交互。透传 AgentLoop 的 StreamEvent。"""

    async def chat(
        self,
        mode: ModeType,
        message: Optional[str] = None,
        selected_text: Optional[str] = None,
        rag_config: Optional[RAGConfig] = None,
        allowed_document_ids: Optional[List[str]] = None,
    ) -> Tuple[str, List[SourceItem]]:
        """非流式交互。返回 (response, sources)。"""

    def cancel_active_request(self) -> None:
        """取消当前活跃的 AgentLoop 执行。"""

    def get_status(self) -> dict:
        """返回会话状态信息。"""
```

### 3.2 SessionLockManager

```python
class SessionLockManager:
    @asynccontextmanager
    async def acquire(self, session_id: str):
        """获取会话级锁。上下文管理器，自动释放。"""

    def cleanup(self, session_id: str) -> None:
        """清理会话锁。Session 结束时调用。"""
```

## 4. 与当前 ChatService 的交互变化

当前 ChatService 承担了大量编排逻辑（模式校验、Scope 获取、Source 验证、Reference 创建）。重构后：

| 职责 | 当前归属 | 重构后归属 |
|------|---------|-----------|
| 模式校验（文档是否就绪） | ChatService | ChatService（不变） |
| Notebook Scope 获取 | ChatService | ChatService（不变） |
| 调用 SessionManager | ChatService | ChatService（不变） |
| 消息持久化 | ChatService | ChatService（不变） |
| Source 验证与 Reference 创建 | ChatService | ChatService（不变） |
| 模式配置构建 | SessionManager -> ModeSelector | SessionManager -> ModeConfigFactory |
| 上下文获取 | SessionManager -> ModeSelector -> Mode | SessionManager -> ContextBuilder |
| 执行 | SessionManager -> ModeSelector -> Mode | SessionManager -> AgentLoop |

ChatService 的接口基本不变，内部调用的 SessionManager 方法签名有调整（新增 rag_config 参数，selected_text 提升为显式参数）。

## 5. 数据所有权

| 数据 | 所有者 | Session 模块的角色 |
|------|--------|-------------------|
| Session 实体 | Application Service / Repository | 消费者 |
| Message 实体 | Application Service / Repository | 消费者（恢复时）、请求方（持久化时） |
| SessionMemory | context 模块 | 调用方：读写历史 |
| ModeConfig | engine 模块 | 调用方：构建配置 |
| AgentLoop | engine 模块 | 调用方：创建和执行 |
| StreamEvent | engine 模块 | 中转者：透传给 API 层 |
| 会话锁 | SessionLockManager | 管理者 |
