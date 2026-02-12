# Improve-6 实施计划

本文档定义任务拆分、依赖关系、实施顺序和每个任务的验收标准。

---

## 1. 任务依赖关系

```
T1 MessageRepository 接口扩展 (modes 过滤 + count)
  |
  +-----> T2 _load_session_history() 分流加载
  |         |
  |         +-----> T4 ExplainMode 迁移到 CondensePlusContextChatEngine
  |         |
  |         +-----> T5 ConcludeMode 迁移到 CondensePlusContextChatEngine
  |         |
  |         +-----> T6 EC 上下文开关实现
  |
  +-----> T3 GET /sessions/{id}/messages 端点实现

T7 DocumentService 删除逻辑拆分 (独立，无前置依赖)

T8 make clean-doc 脚本与孤儿检测 (独立，无前置依赖)

T9 Postman Collection 更新 (依赖 T3, T7 完成)
```

分为两条并行流水线:
- **流水线 A** (记忆架构): T1 -> T2 -> T4/T5 -> T6
- **流水线 B** (API/删除/存储): T3, T7, T8 可并行，T9 收尾

---

## 2. 任务详情

### T1: MessageRepository 接口扩展

**对应设计文档**: [02-memory-architecture.md](./02-memory-architecture.md) 第 4 节, [06-session-messages-api.md](./06-session-messages-api.md) 第 6 节

**涉及文件**:
- `domain/repositories/message_repository.py`
- `infrastructure/repositories/message_repo_impl.py`

**改动内容**:
1. `list_by_session()` 方法增加 `modes: Optional[List[ModeType]]` 和 `offset: int` 参数
2. 实现 SQL 层的 `WHERE mode IN (...)` 过滤
3. 新增 `count_by_session()` 方法，返回符合条件的消息总数

**验收标准**:
- `list_by_session(sid, modes=[ModeType.CHAT, ModeType.ASK])` 只返回 chat/ask 消息
- `list_by_session(sid, modes=None)` 返回所有消息(向后兼容)
- `count_by_session()` 返回正确的计数
- 现有调用方(`_load_session_history` 等)不传 `modes` 时行为无变化

---

### T2: _load_session_history() 分流加载 + 双记忆重命名

**对应设计文档**: [02-memory-architecture.md](./02-memory-architecture.md) 第 2、4 节

**前置依赖**: T1

**涉及文件**:
- `core/engine/session.py`
- `core/engine/selector.py`

**改动内容**:
1. `SessionManager.__init__()`: `_conclude_memory` 重命名为 `_ec_memory`
2. `ModeSelector.__init__()`: `conclude_memory` 参数重命名为 `ec_memory`
3. `_load_session_history()` 改为分流加载:
   - Phase 1: `list_by_session(sid, limit=50, modes=[CHAT, ASK])` -> `_memory`
   - Phase 2: `list_by_session(sid, limit=10, modes=[EXPLAIN, CONCLUDE])` -> `_ec_memory`
4. `end_session()` 中同步重置 `_ec_memory`

**验收标准**:
- Chat/Ask 调用后，`_memory` 中只包含 chat/ask 消息
- Explain/Conclude 调用后，`_ec_memory` 中只包含 explain/conclude 消息
- 两个 memory 之间无交叉污染
- 现有 Chat/Ask 对话体验不受影响

---

### T3: GET /sessions/{id}/messages 端点实现

**对应设计文档**: [06-session-messages-api.md](./06-session-messages-api.md)

**前置依赖**: T1

**涉及文件**:
- `api/models/responses.py`
- `api/routers/sessions.py`
- `application/services/session_service.py`

**改动内容**:
1. `responses.py`: 新增 `MessageResponse` 和 `MessageListResponse` 模型
2. `session_service.py`: 新增 `list_messages()` 方法
3. `sessions.py`: 新增 `list_session_messages` 路由 handler

**验收标准**:
- `GET /sessions/{id}/messages` 返回完整消息列表
- `GET /sessions/{id}/messages?mode=chat,ask` 只返回对应模式消息
- 分页参数 `limit`/`offset` 工作正常
- `pagination.total` 反映过滤后的总数
- 不存在的 session_id 返回 404
- 无效的 mode 值返回 400

---

### T4: ExplainMode 迁移到 CondensePlusContextChatEngine

**对应设计文档**: [02-memory-architecture.md](./02-memory-architecture.md) 第 3.1 节

**前置依赖**: T2

**涉及文件**:
- `core/engine/modes/explain_mode.py`
- `core/engine/selector.py` (传参变更)

**改动内容**:
1. 移除 `super().__init__(llm=llm, memory=None, config=config)` 中的强制 `memory=None`
2. 引入 `CondensePlusContextChatEngine` 替代 `RetrieverQueryEngine`
3. `_refresh_engine()` 中创建 `CondensePlusContextChatEngine.from_defaults(retriever=..., memory=...)`
4. `_process()` 中 `aquery()` 替换为 `achat()`
5. `_stream()` 使用 `astream_chat()` 原生流式接口
6. `_default_config()` 中 `has_memory=True`
7. `ModeSelector._create_mode(EXPLAIN)` 传入 `memory=self._ec_memory`

**验收标准**:
- Explain 模式可以记住最近的对话(5 轮内)
- 追问式交互("再详细说说")能正确理解上下文
- RAG 检索结果(source_nodes)仍然正常返回
- 流式响应正常工作
- selected_text 上下文仍然正确注入
- `_ec_memory` token limit 约束生效(超过时自动裁剪旧消息)

---

### T5: ConcludeMode 迁移到 CondensePlusContextChatEngine

**对应设计文档**: [02-memory-architecture.md](./02-memory-architecture.md) 第 3.2 节

**前置依赖**: T2

**涉及文件**:
- `core/engine/modes/conclude_mode.py`
- `core/engine/selector.py` (传参变更)

**改动内容**:
1. 移除 `self._memory = None` 覆盖语句(第 77 行)
2. `RetrieverQueryEngine.from_args(...)` 替换为 `CondensePlusContextChatEngine.from_defaults(...)`
3. 自定义 `context_prompt` 引导总结行为(替代 `tree_summarize` ResponseMode)
4. `_process()` 中 `aquery()` 替换为 `achat()`
5. `_stream()` 使用 `astream_chat()`
6. `_default_config()` 中 `has_memory=True`
7. `ModeSelector._create_mode(CONCLUDE)` 传入 `memory=self._ec_memory`

**ConcludeMode 特殊注意**: 当前使用 `tree_summarize` 作为 ResponseMode，该模式适合长文档分层总结。迁移到 ChatEngine 后，总结策略需要通过 `context_prompt` 和 `system_prompt` 的提示工程来实现，实现前需要确认总结质量不下降。

**验收标准**:
- Conclude 模式可以记住最近的对话(5 轮内)
- 总结质量与改造前持平(通过同一文档的总结结果对比)
- RAG 检索结果仍然正常
- 流式响应正常工作
- Explain 和 Conclude 共享 `_ec_memory`(在 Explain 中注入的信息可在 Conclude 中被引用)

---

### T6: EC 上下文开关实现

**对应设计文档**: [03-ec-context-switch.md](./03-ec-context-switch.md)

**前置依赖**: T2, T4, T5

**涉及文件**:
- `domain/entities/session.py`
- `infrastructure/models/session_model.py`
- `api/models/requests.py`
- `api/models/responses.py`
- `application/services/chat_service.py`
- `core/engine/session.py`
- `core/engine/modes/chat_mode.py`
- `core/engine/modes/ask_mode.py`
- 数据库迁移脚本

**改动内容**:
1. Session 实体增加 `include_ec_context: bool` 字段
2. ORM 模型和数据库迁移
3. `CreateSessionRequest` 和 `ChatRequest` 增加参数
4. `SessionResponse` 增加返回字段
5. `_load_session_history()` Phase 3: 生成 EC 摘要
6. `SessionManager.chat()` 中注入 EC 摘要到 context
7. ChatMode/AskMode 中检测并拼接 EC 摘要到 system prompt
8. 开关优先级解析(请求级 > Session 级)

**验收标准**:
- 默认(关闭): Chat/Ask 中不包含任何 EC 活动信息
- 开启后: Chat 可以引用近期 Explain/Conclude 的内容
- 请求级开关可以覆盖 Session 级设置
- EC 摘要 token 消耗在预期范围内(约 500 tokens)
- 开关状态在 Session 响应中正确返回

---

### T7: DocumentService 删除逻辑拆分

**对应设计文档**: [04-deletion-endpoint.md](./04-deletion-endpoint.md)

**前置依赖**: 无

**涉及文件**:
- `application/services/document_service.py`
- `api/routers/documents.py`
- `api/routers/library.py`

**改动内容**:
1. `delete_document()` 方法改为软删除(移除 `_delete_document_files()` 调用)
2. 新增 `force_delete_document()` 方法(软删除 + 文件系统删除)
3. `documents.py` 路由调用 `delete_document()` (软删除)
4. `library.py` 路由根据 `force` 参数调用不同方法

**验收标准**:
- `DELETE /documents/{id}`: 索引清除，DB 记录删除，`data/documents/{id}/` 目录保留
- `DELETE /library/documents/{id}?force=false`: 同上，软删除
- `DELETE /library/documents/{id}?force=true`: 全部删除含文件系统
- `DELETE /notebooks/{nid}/documents/{did}`: 行为不变(仅取消关联)

---

### T8: make clean-doc 脚本与孤儿检测

**对应设计文档**: [05-document-storage.md](./05-document-storage.md)

**前置依赖**: 无

**涉及文件** (全部新增):
- `Makefile`
- `scripts/clean-doc.ps1`
- `newbee_notebook/scripts/detect_orphans.py`
- `newbee_notebook/scripts/clean_orphan_documents.py`

**改动内容**:
1. 创建 Makefile，包含 `clean-doc`、`clean-orphans`、`help-clean` targets
2. 创建 PowerShell 版 `clean-doc.ps1` (Windows 兼容)
3. 实现 `detect_orphans.py` 孤儿检测模块
4. 实现 `clean_orphan_documents.py` 批量清理脚本
5. 应用启动入口中调用 `detect_orphan_documents()`

**验收标准**:
- `make clean-doc ID=<uuid>`: 精确删除指定目录，UUID 格式校验通过
- `make clean-doc` 不带 ID: 提示错误，不执行任何删除
- `make clean-doc ID=invalid`: 格式校验失败，不执行删除
- `make clean-orphans`: 正确识别并提示删除孤儿目录
- 应用启动时孤儿检测日志正确输出

---

### T9: Postman Collection 更新

**前置依赖**: T3, T7

**涉及文件**:
- `postman_collection.json`

**改动内容**:
1. 新增 "Get Session Messages" 系列用例(全量/过滤/分页)
2. 更新 "Delete Document" 用例描述(标注为软删除)
3. 更新 "Delete Library Document" 用例(增加 force 参数说明)
4. 更新 "Remove Document from Notebook" 用例描述(标注为仅取消关联)

**验收标准**:
- 所有新增/更新的 Postman 用例可成功执行
- Collection 描述与实际端点行为一致

---

## 3. 实施顺序

```
Phase 1 -- 基础设施层 (无破坏性变更)
+----------------------------------+
| T1: MessageRepository 接口扩展    |  0.5h
| T8: make clean-doc + 孤儿检测    |  1h
+----------------------------------+

Phase 2 -- 核心改造 (记忆架构 + 删除逻辑)
+----------------------------------+
| T2: 分流加载 + 双记忆重命名      |  1h
| T7: 删除逻辑拆分                |  0.5h
| T3: Messages API 端点            |  1h
+----------------------------------+

Phase 3 -- 模式迁移 (核心变更)
+----------------------------------+
| T4: ExplainMode 迁移             |  1.5h
| T5: ConcludeMode 迁移            |  1.5h
+----------------------------------+

Phase 4 -- 增强功能 + 收尾
+----------------------------------+
| T6: EC 上下文开关                |  2h
| T9: Postman Collection 更新      |  0.5h
+----------------------------------+
```

**总预估工时**: 约 9.5 小时

---

## 4. 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| CondensePlusContextChatEngine 与 HybridRetriever 不兼容 | 低 | 高 | T4 阶段先做最小原型验证 |
| ConcludeMode 总结质量下降(失去 tree_summarize) | 中 | 中 | 保留旧代码作 fallback，A/B 对比结果 |
| ChatEngine 内部 memory.put() 与 ChatService DB 持久化冲突 | 低 | 中 | ChatEngine 的 memory 是运行时，DB 是持久化，两者独立 |
| EC 摘要注入导致 Chat/Ask system prompt 过长 | 低 | 低 | 截断策略已限制为约 500 tokens |
| 数据库迁移(T6 新增列)影响现有数据 | 低 | 低 | 使用 ALTER TABLE ... DEFAULT FALSE，无数据丢失 |
