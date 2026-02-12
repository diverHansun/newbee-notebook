# Improve-6 记忆架构重构

本文档覆盖 P-01(Explain/Conclude 无记忆)和 P-02(历史消息跨模式泄漏)两个问题的统一解决方案。

---

## 1. ChatEngine vs QueryEngine 技术选型

### 1.1 LlamaIndex 引擎类型对比

| 维度 | QueryEngine | ChatEngine (CondensePlusContext) |
|------|------------|--------------------------------|
| 状态性 | 无状态，每次 `query()` 独立 | 有状态，内置 `ChatMemoryBuffer` |
| 输入签名 | `query(str)` 返回 `Response` | `chat(message)` 返回 `AgentChatResponse` |
| 检索策略 | 直接用原始 query 文本检索 | 先 condense(浓缩历史+追问为独立问题)再检索 |
| 流式支持 | 需构造时设置 `streaming=True`，无原生 `stream_query()` | 原生 `stream_chat()` / `astream_chat()` |
| 多轮追问 | 不支持("它是什么？"会检索失败) | 支持(condense 将"它"替换为实际实体) |
| 记忆管理 | 无 | 自动 `memory.put(user_msg)` + `memory.put(assistant_msg)` |
| Retriever 兼容 | `RetrieverQueryEngine.from_args(retriever=...)` | `CondensePlusContextChatEngine.from_defaults(retriever=...)` |

### 1.2 CondensePlusContextChatEngine 内部工作流

```
chat(message) 调用链:

Step 1: CONDENSE -- 将对话历史 + 最新消息浓缩为独立问题
  memory.get(input=message) -> chat_history
  若 history 为空或 skip_condense=True，直接使用原始 message
  否则 llm.complete(condense_prompt.format(chat_history, message))
  -> condensed_question (独立的、完整的问题)

Step 2: RETRIEVE -- 用浓缩后的问题检索文档
  retriever.retrieve(condensed_question) -> context_nodes
  -> 应用 node_postprocessors

Step 3: SYNTHESIZE -- 结合上下文 + 对话历史生成回答
  构建 CompactAndRefine response_synthesizer
  注入 context_prompt + system_prompt + chat_history
  synthesizer.synthesize(message, context_nodes) -> response
  memory.put(user_message)
  memory.put(assistant_message)
  -> AgentChatResponse(response, sources, source_nodes)
```

### 1.3 选型结论

Explain/Conclude 从 `RetrieverQueryEngine` 迁移到 `CondensePlusContextChatEngine`，理由:

1. **保留 RAG+ES 检索**: `CondensePlusContextChatEngine` 接受相同的 `BaseRetriever` 接口，现有的 `HybridRetriever` 和 `ScopedRetriever` 可以直接复用。
2. **获得轻量多轮能力**: 通过 `ChatMemoryBuffer(token_limit=2000)` 控制记忆容量，仅保留最近约 5 轮对话。
3. **condense 提升追问检索质量**: 当用户说"能再详细解释一下吗？"，condense 步骤会自动将上次 Explain 的上下文信息融入检索 query，显著提升检索命中率。
4. **原生流式支持**: `astream_chat()` 直接可用，不需要当前 `_stream()` 中的 fallback 逻辑。
5. **记忆自动管理**: ChatEngine 内部自动处理 `memory.put()`，不需要外部手动写入。

---

## 2. 双记忆系统设计

### 2.1 架构总览

```
SessionManager
  |
  +-- _memory: ChatMemoryBuffer          # Chat/Ask 共享记忆
  |     token_limit = 配置值 (默认基于 LLM context_window)
  |     加载来源: DB 中 mode IN (chat, ask) 的消息
  |
  +-- _ec_memory: ChatMemoryBuffer        # Explain/Conclude 共享记忆
  |     token_limit = 2000 (约 5 轮对话)
  |     加载来源: DB 中 mode IN (explain, conclude) 的消息
  |
  +-- ModeSelector
        |
        +-- ChatMode       -> 使用 _memory
        +-- AskMode        -> 使用 _memory
        +-- ExplainMode    -> 使用 _ec_memory
        +-- ConcludeMode   -> 使用 _ec_memory
```

### 2.2 命名变更

| 原名称 | 新名称 | 说明 |
|--------|--------|------|
| `_conclude_memory` | `_ec_memory` | 语义更准确: Explain+Conclude 共享，不再是 Conclude 独占 |

### 2.3 SessionManager 改造

**改造前** (`session.py`):

```python
class SessionManager:
    def __init__(self, llm, session_repo, message_repo, ...):
        self._memory = ChatMemoryBuffer.from_defaults(token_limit=..., llm=llm)
        self._conclude_memory = ChatMemoryBuffer.from_defaults(token_limit=..., llm=llm)
        self._mode_selector = ModeSelector(
            ...,
            memory=self._memory,
            conclude_memory=self._conclude_memory,
        )
```

**改造后**:

```python
# 新增配置常量
EC_MEMORY_TOKEN_LIMIT = 2000  # 约 5 轮对话

class SessionManager:
    def __init__(self, llm, session_repo, message_repo, ...):
        self._memory = ChatMemoryBuffer.from_defaults(
            token_limit=self._memory_token_limit, llm=llm,
        )
        self._ec_memory = ChatMemoryBuffer.from_defaults(
            token_limit=EC_MEMORY_TOKEN_LIMIT, llm=llm,
        )
        self._mode_selector = ModeSelector(
            ...,
            memory=self._memory,
            ec_memory=self._ec_memory,      # 参数名变更
        )
```

### 2.4 ModeSelector 改造

**改造前** (`selector.py`):

```python
class ModeSelector:
    def __init__(self, ..., memory=None, conclude_memory=None):
        self._memory = memory
        self._conclude_memory = conclude_memory or memory
```

**改造后**:

```python
class ModeSelector:
    def __init__(self, ..., memory=None, ec_memory=None):
        self._memory = memory
        self._ec_memory = ec_memory     # 参数名变更

    def _create_mode(self, mode_type):
        if mode_type == ModeType.CHAT:
            return ChatMode(llm=self._llm, memory=self._memory, ...)
        elif mode_type == ModeType.ASK:
            return AskMode(llm=self._llm, memory=self._memory, ...)
        elif mode_type == ModeType.EXPLAIN:
            return ExplainMode(
                llm=self._llm,
                index=self._pgvector_index,
                es_index=self._es_index,
                memory=self._ec_memory,       # 传入 _ec_memory
            )
        elif mode_type == ModeType.CONCLUDE:
            return ConcludeMode(
                llm=self._llm,
                index=self._pgvector_index,
                memory=self._ec_memory,       # 传入 _ec_memory
            )
```

---

## 3. Explain/Conclude 模式迁移

### 3.1 ExplainMode 改造

**改造前**: 使用 `RetrieverQueryEngine`，强制 `memory=None`

**改造后**: 使用 `CondensePlusContextChatEngine`，接收 `_ec_memory`

```python
from llama_index.core.chat_engine import CondensePlusContextChatEngine

class ExplainMode(BaseMode):
    def __init__(self, llm, index=None, es_index=None, memory=None, config=None,
                 similarity_top_k=5):
        # 不再强制 memory=None，接收 _ec_memory
        super().__init__(llm=llm, memory=memory, config=config)
        self._index = index
        self._es_index = es_index
        self._similarity_top_k = similarity_top_k
        self._chat_engine = None
        self._retriever = None

    def _default_config(self):
        return ModeConfig(
            mode_type=ModeType.EXPLAIN,
            has_memory=True,            # 从 False 改为 True
            system_prompt=load_prompt("explain.md"),
            verbose=False,
        )

    async def _refresh_engine(self):
        pg_filters, es_filters, allowed_ids = build_document_filters(
            self.allowed_doc_ids, key="ref_doc_id"
        )
        self._retriever = build_hybrid_retriever(
            pgvector_index=self._index,
            es_index=self._es_index,
            pgvector_top_k=self._similarity_top_k,
            es_top_k=self._similarity_top_k,
            final_top_k=self._similarity_top_k,
            pg_filters=pg_filters,
            es_filters=es_filters,
            allowed_doc_ids=allowed_ids,
        )
        # 核心变更: RetrieverQueryEngine -> CondensePlusContextChatEngine
        self._chat_engine = CondensePlusContextChatEngine.from_defaults(
            retriever=self._retriever,
            llm=self._llm,
            memory=self._memory,        # 使用 _ec_memory
            system_prompt=self._config.system_prompt or load_prompt("explain.md"),
            skip_condense=False,
            verbose=self._config.verbose,
        )

    async def _process(self, message):
        if self.scope_changed():
            await self._refresh_engine()
        query = self._build_enhanced_query(message)
        # 核心变更: aquery -> achat
        response = await self._chat_engine.achat(query)
        # 提取 sources
        sources = []
        source_nodes = getattr(response, "source_nodes", None)
        if source_nodes:
            for n in source_nodes:
                doc_id = extract_document_id(n)
                sources.append({
                    "document_id": doc_id,
                    "chunk_id": getattr(n.node, "node_id", ""),
                    "text": n.node.get_content(),
                    "score": getattr(n, "score", 0.0),
                })
        # 处理 selected_text source
        selection = self.get_selected_text()
        doc_id = self.get_context_document_id()
        if selection and doc_id:
            sources.insert(0, {
                "document_id": doc_id,
                "chunk_id": getattr(self._context, "chunk_id", None) or "user_selection",
                "text": selection,
                "score": 1.0,
            })
        self._last_sources = sources
        # 注意: ChatEngine 内部已自动 memory.put()，无需外部处理
        return response.response

    async def _stream(self, message):
        if self.scope_changed():
            await self._refresh_engine()
        query = self._build_enhanced_query(message)
        # 核心变更: 使用原生 astream_chat
        streaming_response = await self._chat_engine.astream_chat(query)
        async for token in streaming_response.async_response_gen():
            yield token
        # 流式完成后提取 sources
        source_nodes = getattr(streaming_response, "source_nodes", [])
        sources = []
        for n in (source_nodes or []):
            doc_id = extract_document_id(n)
            sources.append({
                "document_id": doc_id,
                "chunk_id": getattr(n.node, "node_id", ""),
                "text": n.node.get_content(),
                "score": getattr(n, "score", 0.0),
            })
        selection = self.get_selected_text()
        doc_id = self.get_context_document_id()
        if selection and doc_id:
            sources.insert(0, {
                "document_id": doc_id,
                "chunk_id": getattr(self._context, "chunk_id", None) or "user_selection",
                "text": selection,
                "score": 1.0,
            })
        self._last_sources = sources

    async def reset(self):
        if self._memory is not None:
            self._memory.reset()
        if self._chat_engine is not None:
            self._chat_engine.reset()
```

### 3.2 ConcludeMode 改造

与 ExplainMode 类似，核心变更点:

1. 移除 `self._memory = None` 覆盖语句
2. `RetrieverQueryEngine.from_args(...)` 替换为 `CondensePlusContextChatEngine.from_defaults(...)`
3. `aquery()` 替换为 `achat()`
4. `_stream()` 使用 `astream_chat()`
5. `has_memory` 配置从 `False` 改为 `True`

**ConcludeMode 的特殊处理**:

当前 ConcludeMode 使用 `tree_summarize` 作为 `response_mode`。迁移到 ChatEngine 后，总结行为通过 `system_prompt` 和 `context_prompt` 引导，不再依赖 `tree_summarize` ResponseMode。

```python
CONCLUDE_SYSTEM_PROMPT = load_prompt("conclude.md")

# 自定义 context_prompt 引导总结行为:
CONCLUDE_CONTEXT_PROMPT = (
    "以下是从知识库检索到的相关文档内容:\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    "请基于以上文档内容，对用户请求的主题进行全面总结。"
    "提取核心观点，按逻辑顺序组织，内容较长则分点列出关键信息。"
)
```

### 3.3 关于 ChatEngine 内部记忆管理的注意事项

`CondensePlusContextChatEngine` 在 `chat()` / `achat()` 完成后会自动调用:

```python
memory.put(ChatMessage(role=MessageRole.USER, content=message))
memory.put(ChatMessage(role=MessageRole.ASSISTANT, content=response))
```

这意味着:
- Mode 的 `_process()` 方法内**不需要**手动操作 memory
- `ChatService` 中的 `_message_repo.create_batch()` 仍然负责 DB 持久化(ChatEngine 的 memory 仅在内存中)
- 两者不冲突: ChatEngine memory 是运行时上下文，DB 是持久化存储

**关键区别**: 当前 ChatMode/AskMode 在 `_process()` 中手动 `self._memory.put()`，而改造后 ExplainMode/ConcludeMode 的 `_memory.put()` 由 ChatEngine 内部自动处理。这两种方式并存是合理的:
- Chat/Ask: 使用 Agent(FunctionAgent/ReActAgent)，Agent 不自动管理 memory，需要外部 put
- Explain/Conclude: 使用 ChatEngine，ChatEngine 自动管理 memory

---

## 4. _load_session_history() 分流加载

### 4.1 改造目标

从 DB 加载消息时按 `mode` 字段分流，Chat/Ask 消息只进 `_memory`，Explain/Conclude 消息只进 `_ec_memory`。

### 4.2 MessageRepository 接口变更

在 `list_by_session()` 方法中增加可选的 `modes` 过滤参数:

```python
# domain/repositories/message_repository.py
class MessageRepository(ABC):
    @abstractmethod
    async def list_by_session(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0,
        modes: Optional[List[ModeType]] = None,    # 新增
    ) -> List[Message]:
        ...
```

```python
# infrastructure/repositories/message_repo_impl.py
async def list_by_session(self, session_id, limit=50, offset=0, modes=None):
    query = select(MessageModel).where(MessageModel.session_id == session_id)
    if modes:
        query = query.where(MessageModel.mode.in_([m.value for m in modes]))
    query = query.order_by(MessageModel.created_at.asc()).limit(limit).offset(offset)
    result = await self._session.execute(query)
    return [self._to_entity(row) for row in result.scalars()]
```

### 4.3 _load_session_history() 改造

**改造前**:

```python
async def _load_session_history(self) -> None:
    if not self._current_session:
        return
    messages = await self._message_repo.list_by_session(
        self._current_session.session_id,
        limit=50,
    )
    self._memory.reset()
    for msg in messages:
        role = LlamaMessageRole.USER if msg.role == MessageRole.USER else LlamaMessageRole.ASSISTANT
        self._memory.put(LlamaChatMessage(role=role, content=msg.content))
```

**改造后**:

```python
async def _load_session_history(self) -> None:
    if not self._current_session:
        return
    sid = self._current_session.session_id

    # Phase 1: 加载 Chat/Ask 消息到 _memory
    ca_messages = await self._message_repo.list_by_session(
        sid, limit=50, modes=[ModeType.CHAT, ModeType.ASK],
    )
    self._memory.reset()
    for msg in ca_messages:
        role = LlamaMessageRole.USER if msg.role == MessageRole.USER else LlamaMessageRole.ASSISTANT
        self._memory.put(LlamaChatMessage(role=role, content=msg.content))

    # Phase 2: 加载 Explain/Conclude 消息到 _ec_memory
    ec_messages = await self._message_repo.list_by_session(
        sid, limit=10, modes=[ModeType.EXPLAIN, ModeType.CONCLUDE],
    )
    self._ec_memory.reset()
    for msg in ec_messages:
        role = LlamaMessageRole.USER if msg.role == MessageRole.USER else LlamaMessageRole.ASSISTANT
        self._ec_memory.put(LlamaChatMessage(role=role, content=msg.content))
```

### 4.4 加载数量说明

| 记忆缓冲区 | 加载条数上限 | 理由 |
|-----------|------------|------|
| `_memory` (Chat/Ask) | 50 条 | 主对话流，需要充分的历史上下文 |
| `_ec_memory` (Explain/Conclude) | 10 条 | 轻量上下文，约 5 轮对话(user+assistant 各 1 条) |

实际可用条数还受 `ChatMemoryBuffer.token_limit` 约束 -- `get()` 方法会从最新消息开始计数，自动裁剪超出 token 限制的旧消息。

---

## 5. 改造影响范围

### 5.1 需要修改的文件

| 文件 | 改动类型 | 改动内容 |
|------|---------|---------|
| `core/engine/session.py` | 重构 | `_conclude_memory` 重命名为 `_ec_memory`; `_load_session_history()` 分流加载 |
| `core/engine/selector.py` | 重构 | `conclude_memory` 参数重命名为 `ec_memory`; `_create_mode()` 传参变更 |
| `core/engine/modes/explain_mode.py` | 重构 | 引擎从 `RetrieverQueryEngine` 改为 `CondensePlusContextChatEngine` |
| `core/engine/modes/conclude_mode.py` | 重构 | 同上; 移除 `self._memory = None` 覆盖 |
| `core/engine/modes/base.py` | 微调 | `ModeConfig` 中 ExplainMode/ConcludeMode 的 `has_memory` 改为 True |
| `domain/repositories/message_repository.py` | 接口扩展 | `list_by_session()` 增加 `modes` 参数 |
| `infrastructure/repositories/message_repo_impl.py` | 实现变更 | `list_by_session()` 增加 `WHERE mode IN (...)` 过滤 |

### 5.2 不需要修改的文件

| 文件 | 理由 |
|------|------|
| `core/engine/modes/chat_mode.py` | Chat 模式不受影响，仍使用 `_memory` |
| `core/engine/modes/ask_mode.py` | Ask 模式不受影响，仍使用 `_memory` |
| `application/services/chat_service.py` | 消息持久化逻辑不变，`mode` 字段已正确记录 |
| `api/routers/chat.py` | API 层不受影响 |

### 5.3 向后兼容性

- DB 中已有的消息记录无需迁移(`mode` 字段已存在且已填充)
- API 接口签名不变(mode 参数通过 `chat()` / `chat_stream()` 的 `mode` 字段传入)
- 已有的 Chat/Ask 对话体验保持不变
- Explain/Conclude 的 API 调用方式不变，但返回质量可能因多轮上下文而有所提升
