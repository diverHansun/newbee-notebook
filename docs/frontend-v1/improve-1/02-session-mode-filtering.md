# 02 - 会话选择器模式过滤：前端行为与后端设计不一致

## 当前问题

在 Chat 面板的会话下拉选择器中，通过 explain（解释）或 conclude（总结）模式创建的会话
也会出现在列表里。选中这些会话后，消息列表为空（因为前端已按 mode 过滤只显示 chat/ask 消息），
造成用户困惑。

## 根因分析

### 后端设计意图：单 Session 多模式共存

后端的架构设计是 **四种模式共享同一个 Session**，通过双记忆缓冲区隔离上下文：

```
Session（模式无关，无 mode 字段）
  |
  |-- _memory 缓冲区 ← chat/ask 消息（主对话记忆）
  |-- _ec_memory 缓冲区 ← explain/conclude 消息（划词上下文记忆）
  |
  |-- include_ec_context: bool
  |     当为 true 且当前模式为 chat/ask 时，
  |     将 _ec_memory 的摘要注入到主对话上下文中
```

关键实现位置：

| 文件 | 行号 | 内容 |
|------|------|------|
| `newbee_notebook/core/engine/session.py` | 27, 48-51 | 双缓冲区初始化 |
| `newbee_notebook/core/engine/session.py` | 105-134 | 按模式加载历史到不同缓冲区 |
| `newbee_notebook/core/engine/session.py` | 156-185 | chat() 中注入 EC 上下文的条件判断 |
| `newbee_notebook/application/services/chat_service.py` | 108-112 | include_ec_context 优先级解析 |

消息按模式分组加载的逻辑（`core/engine/session.py:105-134`）：

```python
# chat/ask 消息 → 主记忆
ca_messages = await self._message_repo.list_by_session(
    sid, limit=50, modes=[ModeType.CHAT, ModeType.ASK])

# explain/conclude 消息 → EC 记忆
ec_messages = await self._message_repo.list_by_session(
    sid, limit=10, modes=[ModeType.EXPLAIN, ModeType.CONCLUDE])
```

EC 上下文注入条件（`core/engine/session.py:170-176`）：

```python
if (include_ec_context
    and effective_mode in (ModeType.CHAT, ModeType.ASK)
    and self._ec_context_summary):
    merged_context["ec_context_summary"] = self._ec_context_summary
```

### 前端实现：违背了后端设计

前端在 `useChatSession.ts` 中的 `sendMessage` 函数对所有模式统一调用 `ensureSession`：

```typescript
const sendMessage = async (message, mode, context) => {
  const sessionId = await ensureSession(message.slice(0, 30));
  // ...
};
```

`ensureSession` 的行为：
- 如果当前有选中的会话 → 复用（正确）
- 如果没有选中的会话 → 创建新会话，标题为消息前30个字符（问题所在）

当用户未选中任何会话就使用 explain/conclude 功能时，会创建标题为
"请解释这段内容" 或 "请总结这段内容" 的新会话。这些会话出现在下拉框中，
但由于消息按 `mode: "chat,ask"` 过滤，选中后显示为空。

### 数据结构确认

```
Session 实体 (domain/entities/session.py)
  - session_id
  - notebook_id
  - title
  - message_count
  - context_summary
  - include_ec_context: bool（控制 EC 上下文是否注入 chat/ask）
  （无 mode 字段 -- 设计如此，非遗漏）

Message 实体 (domain/entities/message.py)
  - message_id
  - session_id
  - mode: ModeType（chat / ask / explain / conclude）
  - role
  - content

数据库 (scripts/db/init-postgres.sql)
  - sessions 表: 无 mode 列，有 include_ec_context BOOLEAN
  - messages 表: 有 mode VARCHAR(20) CHECK (mode IN ('chat','ask','conclude','explain'))
```

## 解决方案

### 推荐方案：前端 explain/conclude 复用当前会话

既然后端设计就是多模式共享 Session，前端应与之对齐。
explain/conclude 不应创建新会话，而应复用当前 Session。

#### 修改逻辑

在 `useChatSession.ts` 的 `sendMessage` 函数中：

1. 当 mode 为 `explain` 或 `conclude` 时：
   - 如果当前有选中的会话 → 直接使用（当前已正确）
   - 如果没有选中的会话 → 自动创建一个通用标题的会话（如"新会话"），
     而不是用 explain/conclude 的消息内容作为标题
   - 或者更好的做法：先创建会话并设为当前会话，再发送消息

2. 会话标题策略调整：
   - chat/ask 模式创建会话时：使用消息前30个字符作为标题（当前行为）
   - explain/conclude 模式：复用已有会话，不单独创建

#### 具体改动

```typescript
// useChatSession.ts - sendMessage 函数内
const sendMessage = async (message, mode, context) => {
  let sessionId: string;

  if (mode === "explain" || mode === "conclude") {
    // explain/conclude: 复用当前会话，或使用最近的会话，或创建通用会话
    sessionId = currentSessionId || await ensureSession("新会话");
  } else {
    // chat/ask: 保持原有逻辑
    sessionId = await ensureSession(message.slice(0, 30));
  }
  // ...
};
```

### 备选方案：后端增加 session_type 字段

如果业务上确实需要将 explain/conclude 的会话与 chat/ask 分离管理
（例如未来需要独立的 EC 会话列表），则可以在 Session 实体上增加类型字段。

但根据当前后端双缓冲区的设计，**同 Session 多模式共存是更合理的方向**。
增加 session_type 字段反而会与后端的共享 Session 设计产生冲突。

## 对架构的影响

- 修改集中在 `useChatSession.ts` 的 `sendMessage` 函数，约 5 行改动
- 不需要后端改动，与后端设计意图完全对齐
- 不需要数据库迁移
- 已有的"孤立" explain/conclude 会话可通过手动删除清理，或在前端做兼容过滤

## 具体修改点

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/lib/hooks/useChatSession.ts` | sendMessage 中 explain/conclude 模式复用当前会话 |

## 待确认事项

1. 当用户没有任何会话时使用 explain/conclude，是否应自动创建一个通用标题的会话？
   还是提示用户先创建会话？
2. 已有的标题为"请解释这段内容"的孤立会话，是否需要做清理或前端兼容处理？
