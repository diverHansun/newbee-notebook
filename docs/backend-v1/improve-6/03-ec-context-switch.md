# Improve-6 EC 上下文开关设计

本文档描述 `include_ec_context` 机制: 一个可选的开关，允许 Chat/Ask 模式在对话时感知最近的 Explain/Conclude 活动。

本文档依赖 [02-memory-architecture.md](./02-memory-architecture.md) 中定义的双记忆系统 (`_memory` + `_ec_memory`) 作为前提。

---

## 1. 设计动机

### 1.1 使用场景

用户在阅读文档时可能产生如下交互序列:

```
[Explain] 用户选中一段文字，请求解释 attention mechanism
[Explain] AI 给出解释
[Chat]    用户切换到 Chat 模式: "刚才解释的 attention mechanism，和 Transformer 有什么关系？"
```

在双记忆系统下，Chat 模式的 `_memory` 中不包含 Explain 的历史 -- 这是正确的隔离行为。但对于上述场景，用户期望 Chat 模式能"知道"刚才发生的 Explain 活动。

### 1.2 设计原则

1. **隔离优先**: 默认关闭，Chat/Ask 记忆保持纯净
2. **摘要注入而非消息混入**: 不将 EC 消息直接加入 `_memory`，而是生成文本摘要注入 system prompt
3. **用户可控**: 通过 API 参数显式启用，不进行隐式注入
4. **token 可预估**: EC 摘要文本长度有上限，不会无限膨胀

---

## 2. 接口设计

### 2.1 开关粒度

提供两个层级的控制:

| 层级 | 配置位置 | 生效范围 | 优先级 |
|------|---------|---------|--------|
| Session 级 | Session 实体属性 | 该 Session 所有后续请求的默认值 | 低 |
| 请求级 | chat/chat_stream 请求参数 | 单次请求 | 高(覆盖 Session 级) |

### 2.2 Session 实体扩展

在 `Session` 实体中增加 `include_ec_context` 字段:

```python
# domain/entities/session.py
class Session:
    session_id: str
    notebook_id: str
    title: Optional[str]
    message_count: int
    include_ec_context: bool = False     # 新增，默认关闭
    created_at: datetime
    updated_at: datetime
```

对应的数据库迁移:

```sql
ALTER TABLE sessions ADD COLUMN include_ec_context BOOLEAN NOT NULL DEFAULT FALSE;
```

### 2.3 API 接口变更

**创建 Session 时设置默认值**:

```
POST /notebooks/{notebook_id}/sessions
{
    "title": "研究笔记",
    "include_ec_context": true    // 可选，默认 false
}
```

**Chat 请求时覆盖**:

```
POST /chat/stream
{
    "session_id": "xxx",
    "message": "刚才解释的内容和 Transformer 有什么关系？",
    "mode": "chat",
    "include_ec_context": true    // 可选，覆盖 Session 级设置
}
```

### 2.4 请求模型变更

```python
# api/models/requests.py
class CreateSessionRequest(BaseModel):
    title: Optional[str] = None
    include_ec_context: bool = False     # 新增

class ChatRequest(BaseModel):
    session_id: str
    message: str
    mode: str = "chat"
    context: Optional[dict] = None
    include_ec_context: Optional[bool] = None    # 新增，None 表示使用 Session 默认值
```

---

## 3. 摘要生成机制

### 3.1 策略选择

两种候选方案:

| 方案 | 实现 | 优点 | 缺点 |
|------|------|------|------|
| A. 直接拼接 | 取最近 N 条 EC 消息，格式化为文本段 | 简单可靠，无额外 LLM 调用 | token 消耗与消息数量正相关 |
| B. LLM 压缩 | 调用 LLM 将 EC 消息压缩为一段摘要 | token 精确控制 | 额外一次 LLM 调用的延迟 |

**选择方案 A(直接拼接)**，理由:
- EC 记忆本身已通过 `_ec_memory` 的 token_limit=2000 约束了总量
- 实际注入时只取最近 3 轮(6 条消息)，截断后的文本约 300-600 tokens
- 避免额外 LLM 调用带来的延迟和成本

### 3.2 摘要生成逻辑

```python
# core/engine/session.py 新增方法

def _build_ec_context_summary(self, ec_messages: List[Message]) -> str:
    """将最近的 Explain/Conclude 消息构建为文本摘要。

    取最近 3 轮对话(6 条消息)，格式化为结构化文本。
    每条消息内容截断到 200 字符以控制 token 消耗。

    Args:
        ec_messages: Explain/Conclude 模式的历史消息列表(按时间升序)

    Returns:
        格式化的摘要文本，为空则返回空字符串
    """
    if not ec_messages:
        return ""

    # 取最近 3 轮 (最多 6 条消息)
    recent = ec_messages[-6:]

    lines = ["[近期文档交互活动]"]
    for msg in recent:
        prefix = "用户" if msg.role == MessageRole.USER else "AI"
        mode_label = "解释" if msg.mode == ModeType.EXPLAIN else "总结"
        content_preview = msg.content[:200]
        if len(msg.content) > 200:
            content_preview += "..."
        lines.append(f"[{mode_label}] {prefix}: {content_preview}")

    return "\n".join(lines)
```

### 3.3 摘要注入时机

摘要在 `_load_session_history()` 完成后生成，存储在 `SessionManager` 的实例变量中:

```python
async def _load_session_history(self) -> None:
    sid = self._current_session.session_id

    # Phase 1: 加载 Chat/Ask 消息 (见 02-memory-architecture.md)
    ca_messages = await self._message_repo.list_by_session(
        sid, limit=50, modes=[ModeType.CHAT, ModeType.ASK],
    )
    self._memory.reset()
    for msg in ca_messages:
        ...

    # Phase 2: 加载 EC 消息 (见 02-memory-architecture.md)
    ec_messages = await self._message_repo.list_by_session(
        sid, limit=10, modes=[ModeType.EXPLAIN, ModeType.CONCLUDE],
    )
    self._ec_memory.reset()
    for msg in ec_messages:
        ...

    # Phase 3: 若开关开启，生成 EC 摘要
    include_ec = getattr(self._current_session, 'include_ec_context', False)
    if include_ec:
        self._ec_context_summary = self._build_ec_context_summary(ec_messages)
    else:
        self._ec_context_summary = ""
```

### 3.4 摘要传递给 Chat/Ask 模式

EC 摘要通过 `context` 参数传递给 Mode，拼接到 system prompt 中:

```python
# core/engine/session.py
async def chat(self, message, mode_type=None, allowed_document_ids=None, context=None):
    ...
    # 如果是 Chat/Ask 模式且有 EC 摘要，追加到 context 中
    effective_mode = mode_type or self._current_mode
    if effective_mode in (ModeType.CHAT, ModeType.ASK) and self._ec_context_summary:
        context = dict(context or {})
        context["ec_context_summary"] = self._ec_context_summary

    response = await self._mode_selector.run(
        message, effective_mode,
        allowed_document_ids=allowed_document_ids,
        context=context,
    )
    ...
```

Chat/Ask 模式的 system prompt 构建中检测并拼接:

```python
# 在 ChatMode / AskMode 的 _process() 中
ec_summary = ""
if self._context and isinstance(self._context, dict):
    ec_summary = self._context.get("ec_context_summary", "")

if ec_summary:
    # 拼接到 system prompt 末尾
    enhanced_system = self._config.system_prompt + "\n\n" + ec_summary
    # 使用 enhanced_system 作为本次调用的 system prompt
```

---

## 4. 开关优先级解析

```python
def _resolve_include_ec_context(
    session: Session,
    request_override: Optional[bool],
) -> bool:
    """解析最终的 include_ec_context 值。

    优先级: 请求级 > Session 级 > 默认值(False)

    Args:
        session: 当前 Session 实体
        request_override: 请求中传入的覆盖值，None 表示不覆盖

    Returns:
        最终生效的布尔值
    """
    if request_override is not None:
        return request_override
    return getattr(session, 'include_ec_context', False)
```

---

## 5. token 预算分析

### 5.1 EC 摘要的 token 消耗估算

- 最近 3 轮 = 6 条消息
- 每条消息内容截断到 200 字符
- 加上格式前缀("[解释] 用户: ")约 15 字符
- 单条消息: 约 215 字符 = ~80 tokens
- 6 条消息 + 标题行: 约 80 * 6 + 20 = ~500 tokens

### 5.2 对 Chat/Ask 主记忆的影响

| 配置项 | 值 |
|--------|-----|
| Chat/Ask `_memory` token_limit | ~8000 tokens (以 32k context_window 的 0.25 计) |
| EC 摘要注入量 | ~500 tokens |
| 摘要占比 | ~6.25% |

占用比例较低，不会显著挤压 Chat/Ask 的历史对话空间。

---

## 6. 需要修改的文件

| 文件 | 改动 |
|------|------|
| `domain/entities/session.py` | Session 实体增加 `include_ec_context` 字段 |
| `infrastructure/models/session_model.py` | ORM 模型增加对应列 |
| `api/models/requests.py` | `CreateSessionRequest` 和 `ChatRequest` 增加参数 |
| `api/models/responses.py` | `SessionResponse` 增加 `include_ec_context` 字段 |
| `application/services/chat_service.py` | 解析开关优先级，传递给 SessionManager |
| `core/engine/session.py` | `_build_ec_context_summary()` 方法; `_load_session_history()` Phase 3; `chat()` 中注入逻辑 |
| `core/engine/modes/chat_mode.py` | 检测并拼接 EC 摘要到 system prompt |
| `core/engine/modes/ask_mode.py` | 同上 |
| 数据库迁移脚本 | `ALTER TABLE sessions ADD COLUMN include_ec_context` |
