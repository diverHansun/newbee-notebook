# Session 模块后端问题分析

## 概述

本文档分析两个后端层面的问题：

1. **Bug：side track 历史消息加载方向错误**（`session_manager.py`）
2. **功能缺失：notebook 创建时未自动创建默认 session**（`notebook_service.py`）

---

## 问题一：side track 加载最旧消息而非最新消息

### 定位

**文件**：`newbee_notebook/core/session/session_manager.py`  
**方法**：`_reload_memory()`，第 213–231 行

```python
async def _reload_memory(self) -> None:
    if not self._current_session:
        return

    main_messages = await self._message_repo.list_after_boundary(
        self._current_session.session_id,
        self._current_session.compaction_boundary_id,
        track_modes=list(self.MAIN_TRACK_MODES),
    )
    side_messages = await self._message_repo.list_by_session(   # ← 问题所在
        self._current_session.session_id,
        limit=12,
        modes=list(self.SIDE_TRACK_MODES),
    )
    ...
```

### 根因

`list_by_session` 在 `message_repo_impl.py` 中的 SQL 实现：

```python
query = (
    select(MessageModel)
    .where(MessageModel.session_id == uuid.UUID(session_id))
    .order_by(MessageModel.created_at.asc())   # ← ASC 升序
    .limit(limit)
    .offset(offset)
)
```

排序方向是 **升序（ASC）**，`LIMIT 12` 取出的是最早创建的 12 条记录，而非最近 12 条。

`SessionMemory.side_max_messages=12` 的 `[-12:]` 截断只是防御性剪裁，在这里是空操作（输入本就 ≤12 条，已经被 SQL 的 LIMIT 截断了）。

### 影响范围

- **单次会话中 explain/conclude 调用超过 12 次**时触发。
- 超过 12 次后，内存中的 side track 装载的是**最早**的 12 条历史，导致近期的 explain/conclude 对话上下文在下一次请求时丢失。
- 典型轻量使用（少量 explain/conclude）不受影响。

### 数据流对比

| 期望行为 | 实际行为 |
|---|---|
| 从 DB 取最近 12 条 explain/conclude 消息 | 从 DB 取最早 12 条 explain/conclude 消息 |
| `ORDER BY created_at DESC LIMIT 12`，反转后装入内存 | `ORDER BY created_at ASC LIMIT 12`，直接装入内存 |

### 修复方案

最终实现采用“仓储层显式支持降序查询”的方式，但没有引入字符串型 `order` 参数，而是新增布尔参数 `descending: bool = False`：

```python
# domain/repositories/message_repository.py
@abstractmethod
async def list_by_session(
    self,
    session_id: str,
    limit: int = 100,
    offset: int = 0,
    modes: Optional[List[ModeType]] = None,
    descending: bool = False,
) -> List[Message]:
    pass
```

```python
# infrastructure/persistence/repositories/message_repo_impl.py
order_columns = (
    (MessageModel.created_at.desc(), MessageModel.id.desc())
    if descending
    else (MessageModel.created_at.asc(), MessageModel.id.asc())
)
query = query.order_by(*order_columns).limit(limit)
```

在 `_reload_memory` 中：

```python
side_messages = await self._message_repo.list_by_session(
    self._current_session.session_id,
    limit=12,
    modes=list(self.SIDE_TRACK_MODES),
    descending=True,
)
side_messages.reverse()   # 恢复时间正序
```

这样做的好处是：

- 接口含义更明确，调用方不需要传裸字符串
- 不会影响现有默认升序语义
- 通过 `created_at desc, id desc` 保证同一时间戳下的顺序稳定

### 验证方法

已补充专门测试 `test_session_manager_side_track_reload.py`：验证 `_reload_memory` 使用 `descending=True` 拉取 side track，并在内存中恢复为时间正序。

---

## 问题二：Notebook 创建时未自动创建默认 Session

### 定位

**文件**：`newbee_notebook/application/services/notebook_service.py`（Notebook 创建逻辑）  
**文件**：`newbee_notebook/api/routers/notebooks.py`，`POST /notebooks`，第 42–57 行

当前 `POST /notebooks` 仅创建 Notebook 实体，不创建任何 Session：

```python
@router.post("", response_model=NotebookResponse, status_code=201)
async def create_notebook(request, service):
    notebook = await service.create(request.title, request.description)
    return _to_response(notebook)
    # Session 数量 = 0，前端取不到任何 session
```

### 业务影响链

```
用户创建 Notebook
  └── 进入 MarkdownViewer（或直接点击 View 查看关联文档）
        └── 选中文字，点击 Explain / Conclude
              └── useChatSession.sendMessage() 被调用
                    ├── sessions.length === 0
                    └── 显示 "请先创建会话" 错误（explainCard）
                          └── 用户必须：退出 viewer → 到 ChatPanel → 手动建会话 → 再回来操作
```

用户在 **没有执行任何"创建会话"操作**的情况下，尝试使用 explain/conclude 功能，遇到了一个需要额外操作步骤才能消除的错误提示。

### 修复方案

**核心原则**：每个 Notebook 至少有一个默认 Session，无需用户手动创建。

#### 后端：在 NotebookService.create 中原子化创建默认 Session

最终实现没有放在路由层补偿，也没有额外注入 `SessionService`，而是直接在 `NotebookService.create()` 中复用已注入的 `session_repo`：

```python
result = await self.notebook_repo.create(notebook)

await self.session_repo.create(Session(notebook_id=result.notebook_id))
await self.notebook_repo.increment_session_count(result.notebook_id)

refreshed = await self.notebook_repo.get(result.notebook_id)
return refreshed or result
```

这样做的原因是：

- `NotebookService` 已经同时持有 `notebook_repo` 和 `session_repo`
- 两步操作共享同一个请求事务，session 创建失败时整个请求会 rollback
- 避免路由层出现“Notebook 已建成但默认 session 没建成”的半成功状态
- 重新读取 notebook 后返回，确保 `session_count` 与数据库一致

> `title=None` 仍然成立，i18n 责任继续保留在前端展示层。

### Session 标题的 i18n 约定

- 后端存储 `title=None`，数据库为 NULL。
- 前端新增 `session-labels.ts`，对已有未命名 session 按创建顺序渲染 `uiStrings.chat.defaultSessionTitle`。
- `generateDefaultSessionTitle(sessions, pattern)` 仍只负责“手动新建 session 时生成下一个默认标题”。

### 对已有会话的兼容性

- 历史 Notebook（已存在会话）：不受影响。
- 历史 Notebook（无会话）：前端的 `ensureSession()` 已有兜底逻辑（见前端分析文档），可补救。

---

## 两个问题的关联

| 问题 | 触发条件 | 严重程度 |
|---|---|---|
| Side track 加载方向错误 | 单 session 内 explain/conclude > 12 次 | 中（上下文截断，回答质量下降） |
| Notebook 无默认 Session | 新建 Notebook 后直接使用 explain/conclude | 高（功能完全不可用，需额外操作） |

两个问题独立修复，不互相依赖。

## 已实施文件

| 文件 | 实现 |
|---|---|
| `newbee_notebook/application/services/notebook_service.py` | 创建 Notebook 后自动创建默认 session，并返回刷新后的 notebook |
| `newbee_notebook/core/session/session_manager.py` | side track 改为降序取最近 12 条，再反转恢复时间正序 |
| `newbee_notebook/domain/repositories/message_repository.py` | 增加 `descending` 参数 |
| `newbee_notebook/infrastructure/persistence/repositories/message_repo_impl.py` | 实现升降序稳定排序 |
| `newbee_notebook/tests/unit/application/services/test_notebook_service_create_default_session.py` | 覆盖默认 session 创建与失败回滚路径 |
| `newbee_notebook/tests/unit/core/session/test_session_manager_side_track_reload.py` | 覆盖 side track 最近 12 条重载行为 |
| `newbee_notebook/tests/unit/core/session/test_session_manager.py` | 同步更新已有 side track 测试契约 |
| `newbee_notebook/tests/integration/test_chat_engine_integration.py` | 更新内存仓储 fake，实现 `descending` 契约 |
