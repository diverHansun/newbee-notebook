# Note-Related-Skills 模块：激活流程与确认机制

## 1. Slash 命令激活流程

### 1.1 端到端流程

```
1. 用户输入: "/note 帮我把第3章的要点整理成笔记"
2. 前端: 检测 /note 前缀，正常发送到 chat endpoint
3. ChatService: 调用 SkillRegistry.match_command(message)
   -> 返回 ("note", "帮我把第3章的要点整理成笔记")
4. ChatService: 获取 NoteSkillProvider，构建 SkillManifest
5. ChatService: 将 manifest.description 追加到 system prompt
6. ChatService: 将 manifest.tools 作为 external_tools 传入 ToolRegistry
7. ChatService: 将 manifest.confirmation_required 传入 AgentLoop
8. AgentLoop: 正常执行，agent 可看到 note 工具并决策调用
9. 流式响应返回给前端
```

### 1.2 消息清理规则

SkillRegistry.match_command 的匹配和清理逻辑：

```python
def match_command(self, message: str) -> tuple[str, str] | None:
    stripped = message.strip()
    for name, provider in self._skills.items():
        cmd = provider.slash_command  # e.g. "/note"
        if stripped == cmd:
            return (name, "")
        if stripped.startswith(cmd + " "):
            return (name, stripped[len(cmd):].strip())
    return None
```

规则：
- 消息以 `/note` 开头，后跟空格或为消息结尾
- 返回的 cleaned_message 去除前缀和前导空格
- 如果用户只输入 `/note`（无后续文本），cleaned_message 为空字符串，agent 将收到空内容并可主动询问用户意图

### 1.3 System Prompt 增强

当 skill 激活时，ChatService 在 system prompt 末尾追加 skill 描述段：

```
---
当前已激活技能：笔记管理
你可以使用以下工具操作笔记和查询书签。在执行修改或删除操作前，请先向用户说明你的计划。
---
```

该段落帮助 agent 理解当前具备的额外能力和使用规范。

### 1.4 /note 不修改 mode

Slash 命令不改变请求的 mode。/note 仍然在 agent mode 下执行（agent mode 是唯一支持 external_tools 的模式）。如果当前不是 agent mode，ChatService 应自动切换到 agent mode。

## 2. 确认机制

### 2.1 需要确认的工具

由 SkillManifest.confirmation_required 声明：

```python
confirmation_required=frozenset({
    "update_note",
    "delete_note",
    "disassociate_note_document",
})
```

### 2.2 确认事件流程

```
1. Agent 决策调用 update_note(note_id=xxx, content="...")
2. AgentLoop 检查: "update_note" in confirmation_required -> 是
3. AgentLoop 产出 ConfirmationRequestEvent:
   {
     "type": "confirmation_request",
     "tool_name": "update_note",
     "tool_args": {"note_id": "xxx", "content": "..."},
     "description": "更新笔记 [标题] 的内容"
   }
4. AgentLoop 暂停当前工具执行，等待确认
5. 前端收到事件，展示确认对话框
6. 用户点击确认或拒绝
7. 前端通过 confirmation callback 回传结果
8. AgentLoop 收到确认结果:
   - 确认: 执行工具，继续流程
   - 拒绝: 返回拒绝结果给 agent，agent 可重新规划
```

### 2.3 ConfirmationRequestEvent

新增 StreamEvent 类型：

```python
@dataclass(frozen=True)
class ConfirmationRequestEvent:
    type: str = "confirmation_request"
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    description: str = ""
    request_id: str = field(default_factory=generate_uuid)
```

### 2.4 确认回传机制

两种可选实现方案：

**方案 A：SSE 双向通道（推荐）**

前端在收到 confirmation_request 后，通过现有 chat endpoint 发送确认消息：

```
POST /api/v1/chat/confirm
{
    "session_id": "xxx",
    "request_id": "confirmation_request.request_id",
    "approved": true
}
```

AgentLoop 通过 asyncio.Event 或 asyncio.Queue 等待确认结果。ChatService 在收到确认请求时将结果传递给等待中的 AgentLoop。

**方案 B：工具返回预览**

Agent 调用工具时，工具不直接执行，而是返回操作预览：

```python
ToolCallResult(
    content="即将更新笔记 [标题]。请确认。",
    metadata={"pending_action": "update_note", "args": {...}}
)
```

Agent 将预览转述给用户，用户确认后 agent 再次调用工具并附加 `confirmed: true` 参数。

**推荐方案 A**：方案 B 需要 agent 理解和遵循两阶段调用协议，增加了 prompt 工程复杂度和出错概率。方案 A 将确认逻辑下沉到系统层，agent 无需感知。

### 2.5 确认超时

如果用户在 3 分钟（180 秒）内未响应确认，AgentLoop 自动取消该工具调用，返回超时信息给 agent。前后端统一使用 180 秒超时。

### 2.6 拒绝后的 agent 行为

工具被拒绝时，AgentLoop 向 agent 反馈：

```
ToolCallResult(content="用户拒绝了此操作。", error="user_rejected")
```

Agent 收到后可以：
- 修改操作内容后重新请求
- 询问用户希望如何调整
- 放弃该操作继续其他任务

## 3. 安全约束

### 3.1 Skill 工具只在 agent mode 可用

ToolRegistry.get_tools 已有模式过滤：external_tools 只在 agent/chat mode 下注入。其他模式（ask、explain、conclude）即使收到 /note 前缀也不会注入工具。

### 3.2 Notebook 作用域限制

NoteSkillProvider 构建工具时通过闭包绑定 notebook_id。agent 的工具调用自动限定在当前 notebook 的文档范围内，无法操作其他 notebook 的数据。

### 3.3 确认机制不可绕过

confirmation_required 是 SkillManifest 的声明式属性，由 AgentLoop 强制执行。agent 无法通过调整参数或多次调用来跳过确认。
