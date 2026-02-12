# Improve-6 Session Messages API 补全

本文档描述 `GET /sessions/{session_id}/messages` 端点的设计，包括响应模型、过滤参数、分页机制。

---

## 1. 缺失分析

### 1.1 当前 Session 相关端点

| 方法 | 路径 | 状态 |
|------|------|------|
| POST | `/notebooks/{notebook_id}/sessions` | 已实现 |
| GET | `/notebooks/{notebook_id}/sessions` | 已实现 |
| GET | `/notebooks/{notebook_id}/sessions/latest` | 已实现 |
| GET | `/sessions/{session_id}` | 已实现 |
| DELETE | `/sessions/{session_id}` | 已实现 |
| **GET** | **`/sessions/{session_id}/messages`** | **缺失** |

### 1.2 底层支撑现状

- `MessageRepository.list_by_session()`: 已实现 DB 查询逻辑
- `Message` 实体: 已有完整字段定义 (`session_id`, `mode`, `role`, `content`, `created_at`)
- `MessageModel` ORM: 已映射到 `messages` 表

缺失的部分:
- **API 路由**: `sessions.py` 中无对应 handler
- **响应模型**: `responses.py` 中无 `MessageResponse` / `MessageListResponse`
- **Service 层方法**: `SessionService` 中无获取消息列表的方法

---

## 2. API 端点设计

### 2.1 获取 Session 消息列表

```
GET /sessions/{session_id}/messages
```

**查询参数**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `mode` | string | 否 | 全部 | 过滤模式，逗号分隔。可选值: `chat`, `ask`, `explain`, `conclude` |
| `limit` | integer | 否 | 50 | 每页条数，范围 1-100 |
| `offset` | integer | 否 | 0 | 偏移量 |

**示例请求**:

```
GET /sessions/00447fbe-a29e-4e22-9d1f-7c05724a9849/messages?mode=chat,ask&limit=20&offset=0
```

**成功响应** (200):

```json
{
    "data": [
        {
            "message_id": "msg-uuid-1",
            "session_id": "00447fbe-...",
            "mode": "chat",
            "role": "user",
            "content": "My name is XiaoMing",
            "created_at": "2026-02-11T10:30:00Z"
        },
        {
            "message_id": "msg-uuid-2",
            "session_id": "00447fbe-...",
            "mode": "chat",
            "role": "assistant",
            "content": "Hello XiaoMing! Nice to meet you...",
            "created_at": "2026-02-11T10:30:05Z"
        }
    ],
    "pagination": {
        "total": 42,
        "limit": 20,
        "offset": 0,
        "has_next": true,
        "has_prev": false
    }
}
```

**错误响应** (404):

```json
{
    "error_code": "session_not_found",
    "message": "Session not found: xxx"
}
```

---

## 3. 响应模型

### 3.1 MessageResponse

```python
# api/models/responses.py 新增

class MessageResponse(BaseModel):
    """单条消息响应模型"""
    message_id: str
    session_id: str
    mode: str               # chat / ask / explain / conclude
    role: str               # user / assistant
    content: str
    created_at: datetime
```

### 3.2 MessageListResponse

```python
class MessageListResponse(BaseModel):
    """消息列表响应模型 (含分页)"""
    data: List[MessageResponse]
    pagination: PaginationInfo
```

---

## 4. mode 过滤参数解析

### 4.1 参数格式

`mode` 参数接受逗号分隔的模式名称字符串:

| 示例 | 含义 |
|------|------|
| 不传 | 返回所有模式的消息 |
| `mode=chat` | 只返回 Chat 模式消息 |
| `mode=chat,ask` | 返回 Chat 和 Ask 模式消息 |
| `mode=explain,conclude` | 返回 Explain 和 Conclude 模式消息 |
| `mode=chat,ask,explain,conclude` | 等同于不传(全部) |

### 4.2 解析逻辑

```python
def _parse_mode_filter(mode_param: Optional[str]) -> Optional[List[ModeType]]:
    """解析 mode 查询参数为 ModeType 列表。

    Args:
        mode_param: 逗号分隔的模式名称字符串，如 "chat,ask"

    Returns:
        ModeType 列表，None 表示不过滤

    Raises:
        HTTPException(400): 包含无效的 mode 名称时
    """
    if not mode_param:
        return None
    modes = []
    for name in mode_param.split(","):
        name = name.strip().lower()
        if not name:
            continue
        try:
            modes.append(ModeType(name))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"无效的 mode 值: '{name}'。可选值: chat, ask, explain, conclude"
            )
    return modes if modes else None
```

---

## 5. 路由实现

```python
# api/routers/sessions.py 新增

@router.get("/sessions/{session_id}/messages", response_model=MessageListResponse)
async def list_session_messages(
    session_id: str = Path(..., description="Session ID"),
    mode: Optional[str] = Query(None, description="过滤模式，逗号分隔: chat,ask,explain,conclude"),
    limit: int = Query(50, ge=1, le=100, description="每页条数"),
    offset: int = Query(0, ge=0, description="偏移量"),
    service: SessionService = Depends(get_session_service),
):
    """获取指定 Session 的消息列表。

    支持按 mode 过滤和分页。消息按 created_at 升序排列。
    """
    # 验证 Session 存在
    session = await service.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    # 解析 mode 过滤
    mode_filter = _parse_mode_filter(mode)

    # 查询消息
    messages, total = await service.list_messages(
        session_id=session_id,
        modes=mode_filter,
        limit=limit,
        offset=offset,
    )

    return MessageListResponse(
        data=[
            MessageResponse(
                message_id=msg.message_id,
                session_id=msg.session_id,
                mode=msg.mode.value if hasattr(msg.mode, 'value') else str(msg.mode),
                role=msg.role.value if hasattr(msg.role, 'value') else str(msg.role),
                content=msg.content,
                created_at=msg.created_at,
            )
            for msg in messages
        ],
        pagination=PaginationInfo(
            total=total,
            limit=limit,
            offset=offset,
            has_next=(offset + limit) < total,
            has_prev=offset > 0,
        ),
    )
```

---

## 6. Service 层

### 6.1 SessionService 新增方法

```python
# application/services/session_service.py 新增

async def list_messages(
    self,
    session_id: str,
    modes: Optional[List[ModeType]] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[List[Message], int]:
    """获取 Session 的消息列表。

    Args:
        session_id: Session ID
        modes: 模式过滤列表，None 表示不过滤
        limit: 每页条数
        offset: 偏移量

    Returns:
        (消息列表, 总条数) 元组
    """
    messages = await self._message_repo.list_by_session(
        session_id=session_id,
        modes=modes,
        limit=limit,
        offset=offset,
    )
    total = await self._message_repo.count_by_session(
        session_id=session_id,
        modes=modes,
    )
    return messages, total
```

### 6.2 MessageRepository 接口补充

```python
# domain/repositories/message_repository.py

class MessageRepository(ABC):
    @abstractmethod
    async def list_by_session(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0,
        modes: Optional[List[ModeType]] = None,
    ) -> List[Message]:
        ...

    @abstractmethod
    async def count_by_session(
        self,
        session_id: str,
        modes: Optional[List[ModeType]] = None,
    ) -> int:
        """返回符合条件的消息总数，用于分页."""
        ...
```

### 6.3 MessageRepository 实现

```python
# infrastructure/repositories/message_repo_impl.py

async def list_by_session(self, session_id, limit=50, offset=0, modes=None):
    query = select(MessageModel).where(MessageModel.session_id == session_id)
    if modes:
        query = query.where(MessageModel.mode.in_([m.value for m in modes]))
    query = query.order_by(MessageModel.created_at.asc())
    query = query.limit(limit).offset(offset)
    result = await self._session.execute(query)
    return [self._to_entity(row) for row in result.scalars()]

async def count_by_session(self, session_id, modes=None):
    query = select(func.count()).select_from(MessageModel).where(
        MessageModel.session_id == session_id
    )
    if modes:
        query = query.where(MessageModel.mode.in_([m.value for m in modes]))
    result = await self._session.execute(query)
    return result.scalar() or 0
```

---

## 7. 与 EC 上下文开关的配合

`GET /sessions/{id}/messages` 端点可以配合 `include_ec_context` 开关使用:

1. 前端获取 Session 详情 → 检查 `include_ec_context` 字段
2. 前端获取消息列表 → 可以通过 `mode` 参数按需过滤:
   - `mode=chat,ask`: 只展示主对话流
   - `mode=explain,conclude`: 只展示文档交互记录
   - 不传 `mode`: 展示所有消息(混合视图)

前端可以根据 `mode` 字段在 UI 中使用不同的样式区分不同模式的消息(如 Explain 消息用不同颜色或图标标注)。

---

## 8. Postman Collection 更新

新增以下测试用例:

| 用例名称 | 方法 | 路径 | 说明 |
|---------|------|------|------|
| Get Session Messages | GET | `/sessions/{id}/messages` | 获取全部消息 |
| Get Session Messages (Chat Only) | GET | `/sessions/{id}/messages?mode=chat` | 过滤 Chat 消息 |
| Get Session Messages (Paginated) | GET | `/sessions/{id}/messages?limit=10&offset=0` | 分页获取 |
| Get Session Messages (EC Only) | GET | `/sessions/{id}/messages?mode=explain,conclude` | 过滤 EC 消息 |

---

## 9. 需要修改的文件

| 文件 | 改动类型 | 改动内容 |
|------|---------|---------|
| `api/models/responses.py` | 新增 | `MessageResponse`, `MessageListResponse` 模型 |
| `api/routers/sessions.py` | 新增 | `list_session_messages` 路由 handler |
| `application/services/session_service.py` | 新增 | `list_messages()` 方法 |
| `domain/repositories/message_repository.py` | 扩展 | `list_by_session()` 增加 `modes`/`offset`; 新增 `count_by_session()` |
| `infrastructure/repositories/message_repo_impl.py` | 实现 | 对应的查询逻辑 |
| `postman_collection.json` | 更新 | 新增消息列表相关测试用例 |
