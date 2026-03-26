# 后端结构化事件改造

## 概述

当前后端 `ConfirmationRequestEvent` 仅包含 `tool_name` 和英文硬编码 `description`, 前端无法据此生成本地化文案。本文档定义后端需要新增的结构化字段和映射注册机制。

## 新增数据结构

### ConfirmationMeta

在 `newbee_notebook/core/skills/contracts.py` 中新增:

```python
@dataclass(frozen=True)
class ConfirmationMeta:
    action_type: str   # create | update | delete | confirm
    target_type: str   # note | diagram | document
```

### SkillDefinition 扩展

在 `SkillDefinition` 上新增 `confirmation_meta` 字段:

```python
@dataclass
class SkillDefinition:
    name: str
    slash_command: str
    description: str
    tools: list[ToolDefinition]
    system_prompt_addition: str = ""
    confirmation_required: frozenset[str] = field(default_factory=frozenset)
    confirmation_meta: dict[str, ConfirmationMeta] = field(default_factory=dict)
    force_first_tool_call: bool = False
    required_tool_call_before_response: str | None = None
```

`confirmation_meta` 的 key 为 tool_name, 与 `confirmation_required` 中的条目一一对应。

## ConfirmationRequestEvent 扩展

在 `agent_loop.py` 的事件生成处, 从 `confirmation_meta` 中查找当前 tool_name 对应的元数据:

```python
meta = self._confirmation_meta.get(tool_name)
yield ConfirmationRequestEvent(
    request_id=request_id,
    tool_name=tool_name,
    action_type=meta.action_type if meta else "confirm",
    target_type=meta.target_type if meta else "unknown",
    args_summary=self._confirmation_args_summary(effective_arguments),
    description=f"Agent requested to run {tool_name}",
)
```

当 `confirmation_meta` 中未找到对应条目时, `action_type` 回退到 `"confirm"`, `target_type` 回退到 `"unknown"`, 保证向后兼容。

## Skill Provider 注册

### Note Skill

文件: `newbee_notebook/skills/note/provider.py`

```python
confirmation_meta={
    "update_note": ConfirmationMeta(action_type="update", target_type="note"),
    "delete_note": ConfirmationMeta(action_type="delete", target_type="note"),
    "disassociate_note_document": ConfirmationMeta(
        action_type="delete", target_type="document"
    ),
},
```

### Diagram Skill

文件: `newbee_notebook/skills/diagram/provider.py`

```python
confirmation_meta={
    "confirm_diagram_type": ConfirmationMeta(
        action_type="confirm", target_type="diagram"
    ),
    "update_diagram": ConfirmationMeta(action_type="update", target_type="diagram"),
    "delete_diagram": ConfirmationMeta(action_type="delete", target_type="diagram"),
},
```

## 完整映射表

| tool_name | action_type | target_type |
|-----------|-------------|-------------|
| `update_note` | `update` | `note` |
| `delete_note` | `delete` | `note` |
| `disassociate_note_document` | `delete` | `document` |
| `confirm_diagram_type` | `confirm` | `diagram` |
| `update_diagram` | `update` | `diagram` |
| `delete_diagram` | `delete` | `diagram` |

## SSE 事件格式

改造前:

```json
{
  "type": "confirmation_request",
  "request_id": "uuid-xxx",
  "tool_name": "delete_diagram",
  "args_summary": { "diagram_id": "d-123" },
  "description": "Agent requested to run delete_diagram"
}
```

改造后:

```json
{
  "type": "confirmation_request",
  "request_id": "uuid-xxx",
  "tool_name": "delete_diagram",
  "action_type": "delete",
  "target_type": "diagram",
  "args_summary": { "diagram_id": "d-123" },
  "description": "Agent requested to run delete_diagram"
}
```

## 数据传递路径

```
SkillProvider.build_definition()
  -> SkillDefinition.confirmation_meta
    -> ChatService.chat_stream() 传递给 AgentLoop
      -> AgentLoop 生成 ConfirmationRequestEvent
        -> SSE 序列化发送到前端
```

`confirmation_meta` 需沿与 `confirmation_required` 相同的路径传递, 在 `session_manager.py` 和 `chat_service.py` 的函数签名中新增该参数。
