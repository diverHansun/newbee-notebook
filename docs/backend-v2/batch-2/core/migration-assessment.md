# 跨模块迁移评估

本文档定义 batch-2 的正式迁移顺序和旧 core 删除顺序。

原则只有一条：

- **分层替换，但目标架构一次定死**

这意味着不会继续给旧 `modes/agent/query_engine` 体系加新能力。

## 1. 旧代码处置总览

### 1.1 `core/engine/`

| 文件/目录 | 当前职责 | 处置 |
|-----------|----------|------|
| `session.py` | 旧 SessionManager | 迁出到 `core/session/` 后删除 |
| `selector.py` | 旧 ModeSelector | 删除 |
| `modes/base.py` | BaseMode 模板 | 删除 |
| `modes/chat_mode.py` | 旧 chat/FunctionAgent 路径 | 删除 |
| `modes/ask_mode.py` | 旧 ask/ReAct 路径 | 删除 |
| `modes/explain_mode.py` | 旧 explain/QueryEngine 路径 | 删除 |
| `modes/conclude_mode.py` | 旧 conclude/QueryEngine 路径 | 删除 |

### 1.2 `core/agent/`

整个目录删除。batch-2 不再保留旧 runner 抽象。

### 1.3 `core/memory/`

旧 memory helper 不再作为 runtime 主模型。需要的少量配置逻辑可被吸收进新 context 模块。

### 1.4 `core/rag/`

保留：

- retriever
- vector store
- embedding

退出 runtime 主线：

- 旧 `generation/query_engine.py`
- 旧 `generation/chat_engine.py`

## 2. 新模块落地顺序

### Phase 0：文档冻结

先冻结：

- mode matrix
- message contract
- tool contract
- retrieval quality gates
- migration phases

### Phase 1：blocking-fix

先交付独立收益项，不依赖 runtime 重构。

### Phase 2：`core/llm`

引入自研 `LLMClient` 和统一消息协议。

### Phase 3：`core/tools`

引入：

- `ToolRegistry`
- `BuiltinToolProvider`
- `knowledge_base`
- 统一工具协议

### Phase 4：`core/context` + `core/session`

先落最小版：

- 双轨 memory
- truncation
- session lock

### Phase 5：`core/engine`，先迁 `agent`

这是新 runtime 的第一条主路径。

### Phase 6：迁移 `ask`

`ask` 切到新 runtime，固定工具集为：

- `knowledge_base`
- `time`

### Phase 7：迁移 `explain / conclude`

切换到 retrieval-required loop：

- 不再使用 QueryEngine
- 默认当前文档 scope
- 最多 3 次 retrieval iteration
- 质量门控决定是否提前 synthesis 或放宽到 notebook scope

### Phase 8：删除旧 core

删除：

- `core/engine/modes/`
- `core/engine/selector.py`
- `core/agent/`
- 旧 `engine/session.py`

### Phase 9：MCP

建立在新 ToolRegistry 之上，只开放给 `agent`。

## 3. 删除顺序

删除顺序必须按新路径切换完成度推进：

1. `chat_mode.py`
2. `ask_mode.py`
3. `explain_mode.py` / `conclude_mode.py`
4. `selector.py`
5. `core/agent/`
6. `old session manager`

也就是说：

- 哪个 mode 先迁完，对应旧 mode 就先停止演进
- 等四个 mode 都迁完，再做目录级删除

## 4. 明确不在 batch-2 的内容

- Skill
- 图片对话
- 多模态消息执行路径

这些放到 batch-3，不混进 core 重构主线。
