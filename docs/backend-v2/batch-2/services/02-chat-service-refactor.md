# ChatService 适配 Core 模块重构变更分析

## 1. 当前架构

### 1.1 ChatService 的职责

ChatService（`application/services/chat_service.py`）当前承担以下职责:

1. **请求预处理**: 校验 session、解析 mode、获取 notebook scope
2. **文档阻塞检查**: `_validate_mode_guard()` 判断是否允许当前模式
3. **执行委托**: 调用 `SessionManager.chat()` / `chat_stream()` 完成交互
4. **Source 后处理**: 合并、校验、过滤、按质量筛选 Source
5. **消息持久化**: 通过 MessageRepository 将 user/assistant 消息写入数据库，通过 ReferenceRepository 持久化引用
6. **流式封装**: 将 SessionManager 的原始文本流封装为结构化 SSE 事件

### 1.2 存储职责分层

| 层 | 运行时内存 | 数据库持久化 |
|---|----------|-----------|
| SessionManager (core) | ChatMemoryBuffer（LlamaIndex 内存，对话上下文） | 启动时从 DB 加载历史 |
| ChatService (application) | 无 | 每轮交互后写入 Message + Reference |

### 1.3 当前依赖关系

```
ChatService
  --> SessionManager (core/engine/session.py)
        --> ModeSelector (core/engine/selector.py)
              --> ChatMode / AskMode / ExplainMode / ConcludeMode
                    --> FunctionAgent / ReActAgent / CondensePlusContextChatEngine
  --> SessionRepository, MessageRepository, ReferenceRepository (持久化)
  --> DocumentRepository, NotebookDocumentRefRepository (文档状态查询)
  --> VectorStoreIndex (通过 session_manager.vector_index 间接获取)
```

### 1.4 关键接口调用

```python
# 会话初始化
await self._session_manager.start_session(session_id=session_id)

# 非流式调用
response_content, sources = await self._session_manager.chat(
    message, mode_type, allowed_document_ids, context, include_ec_context)

# 流式调用 -- chunk 是纯文本或 __PHASE__: 标记
async for chunk in self._session_manager.chat_stream(
    message, mode_type, allowed_document_ids, context, include_ec_context):
    ...

# Source 获取（流式结束后通过副作用获取）
sources = self._session_manager.get_last_sources()
```

## 2. Core 重构后的新架构

### 2.1 新的依赖关系

```
ChatService
  --> SessionManager (core/session/session_manager.py)     [新]
        --> SessionMemory (core/context/)                   [新]
        --> AgentLoop (core/engine/agent_loop.py)           [新]
        --> Tool Registry (core/tools/)                     [增强]
  --> SessionRepository, MessageRepository, ReferenceRepository
  --> DocumentRepository, NotebookDocumentRefRepository
  --> VectorStoreIndex (直接注入，不再通过 SessionManager)
```

### 2.2 接口变更

| 方面 | 当前 | 重构后 |
|------|------|--------|
| 会话初始化 | `start_session(session_id)` | 接口兼容，内部改用 SessionMemory |
| 流式输出格式 | 纯文本 + `__PHASE__:` 标记 | StreamEvent 对象（PhaseEvent, ToolCallEvent, ContentEvent 等） |
| Source 获取 | 流式结束后 `get_last_sources()` | StreamEvent 中直接包含 SourceEvent |
| 工具构建 | SessionManager 内部构建 | ChatService 传入 allowed_doc_ids，SessionManager 内部构建工具 |
| EC 上下文合并 | ChatService 拼接 ec_context_summary | SessionManager 内部通过双轨上下文自动处理 |
| 非流式调用 | `chat()` 返回 (content, sources) | 通过聚合流式结果实现 |

### 2.3 存储职责分层（确认不变）

| 层 | 运行时内存 | 数据库持久化 |
|---|----------|-----------|
| SessionManager (core) | SessionMemory（双轨上下文、分层压缩） | 不直接操作数据库 |
| ChatService (application) | 无 | 每轮交互后写入 Message + Reference |

数据库写入操作继续由 ChatService 通过 MessageRepository 完成。新 SessionManager 只负责运行时的 SessionMemory 管理，不直接调用 Repository 写 DB。这与 core/session 模块设计原则一致: SessionManager 是 "持久化协调者"（告知何时该存），ChatService 是 "持久化执行者"（实际写库）。

## 3. ChatService 需要的具体变更

### 3.1 流式事件处理重构

当前 chat_stream() 处理纯文本 chunk 并自行构造 SSE 事件。重构后，AgentLoop 产出结构化 StreamEvent，ChatService 将其转换为 SSE 协议事件。

当前:

```python
async for chunk in stream:
    phase_stage = self._parse_stream_phase_marker(chunk)
    if phase_stage:
        yield {"type": "thinking", "stage": phase_stage}
        continue
    full_response += chunk
    yield {"type": "content", "delta": chunk}

sources = self._session_manager.get_last_sources()
yield {"type": "sources", "sources": sources}
```

重构后:

```python
async for event in stream:
    if isinstance(event, PhaseEvent):
        yield {"type": "phase", "phase": event.phase}
    elif isinstance(event, ToolCallEvent):
        yield {"type": "tool_call", "tool_name": event.tool_name, "arguments": event.arguments}
    elif isinstance(event, ToolResultEvent):
        yield {"type": "tool_result", "tool_name": event.tool_name, "success": event.success}
    elif isinstance(event, SourceEvent):
        all_sources.extend(event.sources)
        yield {"type": "sources", "sources": event.sources}
    elif isinstance(event, ContentEvent):
        full_response += event.delta
        yield {"type": "content", "delta": event.delta}
    elif isinstance(event, DoneEvent):
        yield {"type": "done"}
    elif isinstance(event, ErrorEvent):
        yield {"type": "error", "error_code": event.code, "message": event.message}
```

关键变化:
- Source 在 ToolResult 后立即产出，不再等流式结束
- 新增 tool_call 和 tool_result 事件，前端可展示工具调用过程
- `__PHASE__` 文本标记被结构化 PhaseEvent 替代

### 3.2 Source 后处理简化

| 逻辑 | 当前位置 | 重构后位置 | 原因 |
|------|---------|-----------|------|
| Source 收集 | `get_last_sources()` 副作用 | AgentLoop 通过 ToolCallResult.sources 直接输出 | Source 作为一等公民 |
| 用户选区合并 `_merge_sources_with_context()` | ChatService | ChatService（保留） | 属于应用层业务逻辑 |
| document_id 校验 `_filter_valid_sources()` | ChatService | ChatService（保留） | 依赖 DocumentRepository |
| 分数过滤 `_filter_sources_by_mode_quality()` | ChatService | 可移入 RAG Tool 内部 | 检索质量属于工具职责 |
| 回退逻辑 `_restore_ask_display_sources_if_empty()` | ChatService | ChatService（保留，简化） | 显示策略属于应用层 |

### 3.3 EC 上下文合并移除

当前 ChatService 负责拼接 ec_context_summary:

```python
effective_include_ec_context = (
    include_ec_context if include_ec_context is not None
    else bool(getattr(session, "include_ec_context", False))
)
```

重构后:
- 双轨上下文（Main track: Agent/Ask, Side track: Explain/Conclude）由 context 模块 SessionMemory 自动管理
- Side track 可读取 Main track（只读），Main track 看不到 Side track
- ChatService 不再需要 `include_ec_context` 参数
- ChatService 不再传递 `ec_context_summary`

### 3.4 非流式路径统一

当前非流式 `chat()` 有 stream fallback 机制:

```python
try:
    response_content, sources = await self._session_manager.chat(...)
except Exception:
    if self._is_llm_transport_error(exc):
        response_content, sources = await self._chat_via_stream_fallback(...)
```

重构后，AgentLoop 统一使用流式路径。非流式接口通过聚合流式结果实现:

```python
async def chat(self, ...):
    full_response = ""
    all_sources = []
    async for event in self._session_manager.chat_stream(...):
        if isinstance(event, ContentEvent):
            full_response += event.delta
        elif isinstance(event, SourceEvent):
            all_sources.extend(event.sources)
    return full_response, all_sources
```

消除非流式/流式双路径维护，不再需要 `_is_llm_transport_error()` 和 `_chat_via_stream_fallback()`。

### 3.5 _get_context_chunks() 保留并调整注入方式

`_get_context_chunks()` 通过 pgvector 按 chunk_index 获取选中文本的前后邻居 chunk（idx-1, idx, idx+1），为 Explain/Conclude 模式提供更完整的上下文。这与 RAG Tool 的语义检索是不同的操作:

- RAG Tool: 语义检索，基于 query 搜索整个文档库
- `_get_context_chunks()`: 位置检索，基于 chunk_index 获取选中文本周围的上下文

此功能保留在 ChatService，但调整 VectorStoreIndex 的获取方式:
- 当前: 通过 `session_manager.vector_index` 间接获取
- 重构后: 在 ChatService 初始化时直接注入 pgvector_index

### 3.6 阻塞逻辑修复

参见 [01-blocking-fix.md](./01-blocking-fix.md)。此修复独立于 core 模块重构，可提前实施。

## 4. 可删除的代码

重构后 ChatService 中以下代码可删除:

| 方法/属性 | 原因 |
|-----------|------|
| `_parse_stream_phase_marker()` | StreamEvent 替代 `__PHASE__` 文本标记 |
| `_chat_via_stream_fallback()` | 统一流式路径，非流式通过聚合实现 |
| `_is_llm_transport_error()` | 不再需要流式回退判断 |
| `STREAM_PHASE_MARKER_PREFIX` | `__PHASE__` 标记不再使用 |
| `NONSTREAM_STREAM_FALLBACK_CHUNK_TIMEOUT_SECONDS` | 回退路径移除 |

## 5. SessionService 变更

SessionService（`application/services/session_service.py`）变更较小:

### 5.1 update_context_summary 方法

当前由外部调用来更新会话摘要。重构后，上下文压缩（包括异步摘要生成）由 context 模块内部管理。SessionService 的 `update_context_summary()` 方法保留，但调用时机从外部驱动变为 context 模块的异步摘要回调。

### 5.2 list_messages 的 modes 过滤

当前支持按 ModeType 过滤消息。重构后双轨模型的消息仍然标记 mode，此接口无需变更。

## 6. 不变的服务

以下 5 个服务不依赖 core 模块，无需变更:

| 服务 | 职责 |
|------|------|
| DocumentService | 文档上传、状态管理、内容读取、删除 |
| NotebookDocumentService | notebook-document 关联管理、处理任务触发 |
| NotebookService | notebook CRUD、文档引用管理 |
| LibraryService | library CRUD、文档列表 |
| AppSettingsService | 键值配置 CRUD |

## 7. 依赖注入变更

当前:

```python
ChatService(
    session_repo, notebook_repo, reference_repo,
    document_repo, ref_repo, message_repo,
    session_manager,  # core/engine/session.py SessionManager
)
```

重构后:

```python
ChatService(
    session_repo, notebook_repo, reference_repo,
    document_repo, ref_repo, message_repo,
    session_manager,  # core/session/session_manager.py 新 SessionManager
    pgvector_index,   # 直接注入，不再通过 session_manager 间接获取
)
```

新 SessionManager 内部组合了 ContextBuilder、AgentLoop、ToolRegistry，对 ChatService 透明。

## 8. 迁移策略

ChatService 重构应在 core 模块全部完成后进行。阻塞逻辑修复（01-blocking-fix.md）可提前独立实施。

### 迁移顺序

1. **阻塞逻辑修复**（独立，可先行）: 修改 `_validate_mode_guard()`，增加 warning 事件
2. **新 SessionManager 接口稳定后**: 修改依赖注入，替换 SessionManager 类型
3. **StreamEvent 定义完成后**: 重写 `chat_stream()` 的事件处理逻辑
4. **Source 处理简化**: 根据 ToolCallResult.sources 的实际输出调整后处理链
5. **清理废弃代码**: 删除 `_parse_stream_phase_marker`、`_chat_via_stream_fallback` 等
6. **API 层适配**: chat.py router 增加新 SSE 事件类型支持

### 验证标准

- 所有 4 种模式的流式和非流式交互正常
- 部分文档处理中时 Agent/Ask 可使用已完成文档
- CONVERTED 文档的 Explain/Conclude 返回明确的 "索引未构建" 提示
- SSE 事件流包含 tool_call、tool_result、sources 等新事件类型
- warning 事件在前端正确展示
- 消息持久化和 Reference 持久化不受影响
