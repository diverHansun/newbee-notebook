# Note-Related-Skills 模块：架构设计

## 1. 架构总览

```
用户输入: "/note 帮我创建一个关于第3章的笔记"
                    |
                    v
            ChatService
              |  解析 /note 前缀
              |  调用 SkillRegistry.match_command()
              v
          SkillRegistry
              |  返回 (SkillManifest, "帮我创建一个关于第3章的笔记")
              v
          SessionManager.chat_stream(...)
              |  透传 external_tools / system_prompt_addition / confirmation_required
              v
          ToolRegistry.get_tools(external_tools=manifest.tools)
              |  将 skill 工具注入到本次请求的 agent 工具列表
              v
          AgentLoop
              |  agent 看到 note 工具 + system prompt 补充说明
              |  决策调用 create_note / list_marks 等
              v
          ToolDefinition.execute()
              |  调用 NoteService / MarkService
              |  如果工具在 confirmation_required 集合中
              |  -> 产出 ConfirmationRequestEvent
              |  -> 通过 ConfirmationGateway 等待确认 -> 执行或取消
              v
          StreamEvent 序列 -> 前端
```

## 2. 核心组件

### 2.1 SkillManifest

```python
@dataclass(frozen=True)
class SkillManifest:
    name: str
    slash_command: str
    description: str
    tools: list[ToolDefinition]
    system_prompt_addition: str = ""
    confirmation_required: frozenset[str]
```

字段说明：

| 字段 | 说明 |
|------|------|
| name | skill 标识符，如 "note" |
| slash_command | 触发命令，如 "/note" |
| description | skill 描述，用于内部标识与日志 |
| tools | 该 skill 提供的 ToolDefinition 列表 |
| system_prompt_addition | 注入到当次会话 system prompt 末尾的说明文本 |
| confirmation_required | 需要用户确认的工具名称集合 |

SkillManifest 是不可变的值对象。每次请求由 Provider 根据上下文重新构建。

### 2.2 SkillRegistry

```python
class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, SkillProvider] = {}

    def register(self, provider: SkillProvider) -> None
        """注册一个 SkillProvider"""

    def match_command(self, message: str) -> tuple[SkillProvider, str, str] | None
        """
        匹配消息中的 slash 命令前缀。
        返回 (provider, activated_command, cleaned_message) 或 None。
        匹配规则：消息以 "/<skill_name>" 开头，后跟空格或结尾。
        """
```

设计要点：

- SkillRegistry 持有 Provider 而非 Manifest。Manifest 需要请求级上下文（notebook_id）才能构建。
- match_command 只做前缀匹配和消息清理，不构建 Manifest。
- 注册在应用启动时完成，运行时 SkillRegistry 是只读的。

### 2.3 SkillProvider 接口

```python
class SkillProvider(ABC):
    @property
    @abstractmethod
    def skill_name(self) -> str: ...

    @property
    @abstractmethod
    def slash_commands(self) -> list[str]: ...

    @abstractmethod
    def build_manifest(self, context: SkillContext) -> SkillManifest: ...
```

SkillProvider 是构建 SkillManifest 的工厂。每个 skill 实现一个 Provider。

### 2.4 SkillContext

```python
@dataclass(frozen=True)
class SkillContext:
    notebook_id: str
    activated_command: str
    selected_document_ids: list[str] = field(default_factory=list)
```

请求级上下文，传递给 Provider 用于构建工具定义。当前实现只要求 notebook 作用域、触发命令和用户已选文档，不额外引入 session 级状态。

### 2.5 NoteSkillProvider

```python
class NoteSkillProvider(SkillProvider):
    def __init__(
        self,
        note_service: NoteService,
        mark_service: MarkService,
    ):
        ...

    @property
    def skill_name(self) -> str:
        return "note"

    @property
    def slash_commands(self) -> list[str]:
        return ["/note"]

    def build_manifest(self, context: SkillContext) -> SkillManifest:
        return SkillManifest(
            name="note",
            slash_command="/note",
            description="笔记和书签管理技能",
            system_prompt_addition="当前已激活 /note。你可以查询、创建、编辑、删除笔记，查询书签，并在修改性操作前等待用户确认。",
            tools=self._build_tools(context),
            confirmation_required=frozenset({"update_note", "delete_note", "disassociate_note_document"}),
        )
```

## 3. 与现有模块的集成点

### 3.1 ChatService 集成

ChatService 是 skill 激活的入口。在处理用户消息时增加 skill 检测逻辑：

```python
# ChatService.handle_chat_request() 中
skill_match = self._skill_registry.match_command(user_message)
if skill_match:
    provider, activated_command, cleaned_message = skill_match
    context = SkillContext(
        notebook_id=notebook_id,
        activated_command=activated_command,
        selected_document_ids=source_document_ids or [],
    )
    manifest = provider.build_manifest(context)
    # cleaned_message 替换原始消息
    # 强制使用 agent mode
    # manifest.tools 通过 external_tools 注入
    # manifest.system_prompt_addition 追加到 system prompt
```

对齐到现有代码后，ChatService 负责 slash 检测和参数组装，SessionManager 负责透传运行时配置，SkillRegistry 不直接依赖 session 对象。

### 3.2 ToolRegistry 集成

现有 ToolRegistry.get_tools() 已支持 external_tools 参数：

```python
async def get_tools(
    self,
    mode: str,
    external_tools: Iterable[ToolDefinition] | None = None,
) -> list[ToolDefinition]:
```

Skill 的工具通过 external_tools 注入，不修改 ToolRegistry 内部逻辑。external_tools 只在 agent 模式下生效（已有判断）。

### 3.3 AgentLoop 集成（确认机制）

AgentLoop 在执行工具调用时需要检查是否需要确认：

```python
# AgentLoop 工具执行逻辑中
if tool_name in active_skill_confirmation_set:
    yield ConfirmationRequestEvent(
        tool_name=tool_name,
        args_summary=safe_args_summary,
        description="agent 想要执行的操作描述",
    )
    confirmation = await confirmation_gateway.wait(request_id)
    if not confirmation.approved:
        # 将拒绝信息反馈给 agent
        tool_result = ToolCallResult(content="用户拒绝了此操作", error="user_rejected")
    else:
        tool_result = await tool.execute(tool_args)
```

confirmation_required 集合通过 SkillManifest 传递给 AgentLoop；真正的等待与解析由 `ConfirmationGateway` 承担。

## 4. 与 batch-4 的延续关系

| 组件 | batch-3 状态 | batch-4 扩展方向 |
|------|-------------|-----------------|
| SkillManifest | 硬编码在 NoteSkillProvider 中 | 从 SKILL.md frontmatter 解析生成 |
| SkillRegistry | 启动时手动注册 NoteSkillProvider | 扫描 skills/ 目录自动发现和注册 |
| SkillProvider | 只有 NoteSkillProvider | 多个 Provider（思维导图、summarize 等） |
| SkillContext | notebook_id + activated_command + selected_document_ids | 可扩展更多上下文字段 |
| 确认机制 | 基于 frozenset 声明 | 可扩展为更细粒度的权限模型 |
| slash 命令 | 仅 /note | 支持 /mindmap、/summarize 等 |
