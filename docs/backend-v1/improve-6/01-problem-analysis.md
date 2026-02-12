# Improve-6 问题分析

## 1. 问题一: Explain/Conclude 模式无记忆能力

### 1.1 现象

Explain 和 Conclude 模式每次调用完全独立，不保留任何对话历史。用户无法进行如下交互:

```
[Explain-1] 用户: 请解释 attention mechanism
[Explain-1] AI: Attention mechanism 是一种...
[Explain-2] 用户: 能再详细说说 self-attention 吗？
[Explain-2] AI: (完全不记得上一轮的内容，无法理解"再详细"的指代)
```

### 1.2 代码证据

**ExplainMode** (`core/engine/modes/explain_mode.py`):

```python
class ExplainMode(BaseMode):
    def __init__(self, llm, index, es_index, memory=None, ...):
        # 第 83 行: 强制将 memory 设为 None
        super().__init__(llm=llm, memory=None, config=config)
```

- 构造函数中 `memory=None` 被硬编码传入 `super().__init__()`
- 使用 `RetrieverQueryEngine`，该引擎本身不具备对话记忆能力
- `_process()` 调用 `self._query_engine.aquery(query)` 为纯单轮 query

**ConcludeMode** (`core/engine/modes/conclude_mode.py`):

```python
class ConcludeMode(BaseMode):
    def __init__(self, llm, index, memory=None, ...):
        super().__init__(llm=llm, memory=memory, config=config)
        # 第 77 行: 接收了 memory 但立即覆盖为 None
        self._memory = None
```

- 虽然接收了 `_conclude_memory` 参数，但在 `__init__` 中被 `self._memory = None` 覆盖
- 同样使用 `RetrieverQueryEngine`(变量名为 `_chat_engine` 但实际类型是 QueryEngine)
- `_process()` 调用 `self._chat_engine.aquery(query)` 为纯单轮 query

**ModeSelector** (`core/engine/selector.py`):

```python
def _create_mode(self, mode_type):
    elif mode_type == ModeType.CONCLUDE:
        return ConcludeMode(
            llm=self._llm,
            index=self._pgvector_index,
            memory=self._conclude_memory,  # 传入了但在 ConcludeMode 中被丢弃
        )
    elif mode_type == ModeType.EXPLAIN:
        return ExplainMode(
            llm=self._llm,
            index=self._pgvector_index,
            es_index=self._es_index,
            # 没有传入 memory 参数
        )
```

### 1.3 与设计文档的差异

`docs-plan/architecture-guide.md` 中描述的双上下文系统:
- 系统 A: Chat + Ask 共享记忆 -- 实现一致
- 系统 B: Conclude + Explain 共享记忆 -- **实现不一致**，两者都是完全无状态

### 1.4 影响

1. 用户无法在 Explain/Conclude 模式中追问、细化或纠正 AI 的回答
2. 每次都需要重新描述完整上下文，交互效率低
3. `CondensePlusContextChatEngine` 的 condense 步骤无法生效(没有历史可以 condense)，导致代词引用类追问("它是什么？""再详细说说")的检索质量低下

### 1.5 根因

历史实现中将 Explain/Conclude 定位为"单次工具调用"而非"轻量对话"，因此选择了无状态的 `RetrieverQueryEngine`。同时 `_conclude_memory` 的创建和传递链路存在断裂(被 `self._memory = None` 覆盖)。

---

## 2. 问题二: 历史消息跨模式泄漏

### 2.1 现象

在 test-2 测试中发现: 在 Explain 模式中注入的关键词 `RAINBOW-UNICORN-42`，在随后的 Ask 模式中被正确回忆。这意味着 Explain/Conclude 产生的消息泄漏到了 Chat/Ask 的对话上下文中。

### 2.2 代码证据

**`_load_session_history()`** (`core/engine/session.py` 第 102-115 行):

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

关键问题:
- `list_by_session()` 加载该 session 下**所有模式**的最近 50 条消息
- 所有消息无差别地灌入 `self._memory`(Chat/Ask 共享的记忆缓冲区)
- 没有按 `msg.mode` 字段进行过滤

**消息持久化路径** (`application/services/chat_service.py` 第 148, 276 行):

```python
# chat() 和 chat_stream() 中，所有模式的消息都执行持久化:
user_msg = Message(session_id=session_id, mode=mode_enum, role=MessageRole.USER, content=message)
assistant_msg = Message(session_id=session_id, mode=mode_enum, role=MessageRole.ASSISTANT, content=response_content)
await self._message_repo.create_batch([user_msg, assistant_msg])
```

消息表中 `mode` 字段已正确记录，但加载时未利用。

### 2.3 泄漏链路

```
Explain/Conclude 调用
    |
    v
ChatService.chat() / chat_stream() 持久化消息到 DB (mode=explain/conclude)
    |
    v
下一次 Chat/Ask 调用
    |
    v
SessionManager.start_session() -> _load_session_history()
    |
    v
从 DB 加载最近 50 条消息 (不过滤 mode)
    |
    v
所有消息注入 self._memory (Chat/Ask 共享的 ChatMemoryBuffer)
    |
    v
Chat/Ask 的 LLM 上下文中可见 Explain/Conclude 的对话内容
```

### 2.4 影响

1. Chat/Ask 上下文被 Explain/Conclude 的不相关内容稀释，降低对话质量
2. 额外 token 消耗: Explain 一次解释可能产生 500-1000 tokens，多次 Explain 后占用大量 memory 空间
3. LLM 可能混淆不同模式间的语境("你上次解释的 attention mechanism"出现在 Chat 对话中)
4. 违背了"双记忆系统隔离"的设计意图

### 2.5 根因

`_load_session_history()` 在查询数据库时缺少 `mode` 过滤条件。消息表的 `mode` 字段仅在写入时使用，加载时被忽略。

---

## 3. 问题三: 删除端点语义不清晰

### 3.1 现象

当前三个删除相关端点的语义边界模糊:

| 端点 | 期望语义 | 当前实际行为 |
|------|---------|------------|
| `DELETE /documents/{id}` | 软删除: 清除索引数据，保留原文件和 markdown | 硬删除: 清索引 + 删文件 + 删 DB 记录 |
| `DELETE /library/documents/{id}` | 硬删除(force 时): 删除一切含文件系统 | 与上方完全相同(调用同一个 service 方法) |
| `DELETE /notebooks/{id}/documents/{doc_id}` | 取消 notebook-document 关联 | 当前行为正确 |

### 3.2 代码证据

**两个端点调用同一个方法**:

`api/routers/documents.py`:
```python
@router.delete("/documents/{document_id}")
async def delete_document(document_id, force=Query(False)):
    await service.delete_document(document_id, force=force)
```

`api/routers/library.py`:
```python
@router.delete("/library/documents/{document_id}")
async def delete_library_document(document_id, force=Query(False)):
    await service.delete_document(document_id, force=force)
```

两者都调用 `DocumentService.delete_document()`，该方法执行完整的硬删除:
1. `mark_source_deleted()` 软标记聊天引用
2. `delete_by_document()` 删除 notebook 关联
3. `delete_document_nodes_task.delay()` 异步删除向量/ES 节点
4. **`_delete_document_files()`** 删除文件系统 `data/documents/{id}/`
5. `document_repo.delete()` 删除 DB 记录

### 3.3 影响

1. 用户无法实现"只清除索引重新处理"的操作(例如索引损坏时想重建)
2. `DELETE /documents/{id}` 的破坏力过大，与常见 REST 语义不符
3. 两个端点行为完全相同，`/library/documents/{id}` 的存在意义不明确

### 3.4 根因

早期实现时未区分"删除文档数据记录"和"删除文档物理文件"两个层次的操作，统一使用了同一个全量删除方法。

---

## 4. 问题四: Session Messages API 缺失

### 4.1 现象

`GET /sessions/{session_id}/messages` 端点未实现。前端无法获取指定 session 的历史对话记录。

### 4.2 代码证据

`api/routers/sessions.py` 中已有端点:

| 方法 | 路径 | 状态 |
|------|------|------|
| POST | `/notebooks/{notebook_id}/sessions` | 已实现 |
| GET | `/notebooks/{notebook_id}/sessions` | 已实现 |
| GET | `/notebooks/{notebook_id}/sessions/latest` | 已实现 |
| GET | `/sessions/{session_id}` | 已实现 |
| DELETE | `/sessions/{session_id}` | 已实现 |
| **GET** | **`/sessions/{session_id}/messages`** | **缺失** |

底层 `MessageRepository.list_by_session()` 已实现数据库查询，但无 API 路由暴露。

`api/models/responses.py` 中缺少 `MessageResponse` 和 `MessageListResponse` 响应模型。

### 4.3 影响

1. 前端恢复会话时无法展示历史对话
2. 无法按模式过滤展示(只看 Chat 消息 / 只看 Explain 消息)
3. 无法实现对话记录的分页浏览
4. 测试工具(Postman)无法验证消息持久化的正确性

### 4.4 根因

Session CRUD 端点在早期开发中优先实现，消息查询端点被遗漏。

---

## 5. 问题五: docker compose down -v 后文档存储不一致

### 5.1 现象

执行 `docker compose down -v` 删除数据卷后:
- PostgreSQL 和 Elasticsearch 中的文档元数据、索引数据全部丢失
- 存储在宿主机 `data/documents/` 目录下的 PDF 原文件、Markdown、图片资产仍然存在
- 产生"孤儿文件": 文件系统中存在但数据库中无记录的文档目录

### 5.2 代码证据

`docker-compose.yml` 中的挂载配置:

```yaml
services:
  celery-worker:
    volumes:
      - ./:/app  # 整个项目目录挂载
```

`DOCUMENTS_DIR` 默认值为 `data/documents`(相对于 `/app`)，文档写入宿主机的项目目录而非 Docker 命名卷。

### 5.3 影响

1. `docker compose down -v` 后重新启动，系统显示空的文档库，但磁盘上存在大量孤儿文件
2. 长期累积浪费磁盘空间(单个 PDF 文档处理后可能占用 50MB+)
3. 无法通过 API 管理这些遗留文件

### 5.4 根因

Docker 命名卷(`postgres_data`, `elasticsearch_data`)和宿主机 bind mount(`./:/app`)的生命周期不同。`-v` 只删除命名卷，不影响 bind mount 映射的宿主机目录。

本阶段采用的方案: 继续使用 bind mount(保持开发调试便利性)，但补充精确清理工具。

---

## 6. 结论与治理方向

| 编号 | 问题 | 治理方向 | 对应设计文档 |
|------|------|---------|------------|
| P-01 | Explain/Conclude 无记忆 | 迁移到 CondensePlusContextChatEngine + 共享 _ec_memory | 02-memory-architecture.md |
| P-02 | 历史消息跨模式泄漏 | _load_session_history() 按 mode 分流加载 | 02-memory-architecture.md |
| P-03 | 删除端点语义不清晰 | 拆分软删除(清索引)和硬删除(含文件系统) | 04-deletion-endpoint.md |
| P-04 | Session Messages API 缺失 | 新增 GET /sessions/{id}/messages 端点 | 06-session-messages-api.md |
| P-05 | docker compose down -v 后文档孤儿 | make clean-doc 精确删除 + 启动时孤儿检测 | 05-document-storage.md |

P-01 和 P-02 存在强耦合关系(都涉及记忆系统改造)，合并在同一份设计文档中处理。EC 上下文开关作为 P-01/P-02 之上的增强功能，独立为 03 号文档。
