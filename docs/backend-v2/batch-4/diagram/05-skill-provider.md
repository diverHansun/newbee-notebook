# Skill 集成

## 前置条件

本文档描述的 DiagramSkillProvider 依赖 batch-3 note-related-skills 提供的以下基础设施：

- `SkillProvider` 协议
- `SkillManifest` 数据类
- `SkillContext` 数据类
- `SkillRegistry.match_command()`
- `ConfirmationGateway`（AgentLoop 确认暂停机制）
- `ConfirmationRequestEvent`（SSE 事件）
- ChatService 中的 slash 命令检测与工具注入逻辑

以上组件在 batch-3 已实现，batch-4 直接复用。

## 统一命令策略

- batch-4 图表技能统一使用单入口命令：`/diagram`
- 不再拆分 `/mindmap`、`/flowchart`、`/sequence` 作为入口命令
- 具体图表类型由 Agent 从用户 prompt 判断；若不明确，先触发确认卡片，再创建图表

## DiagramSkillProvider

```python
DIAGRAM_SLASH_COMMAND = "/diagram"


class DiagramSkillProvider(SkillProvider):
    def __init__(self, diagram_service: DiagramService) -> None:
        self._service = diagram_service

    @property
    def skill_name(self) -> str:
        return "diagram"

    @property
    def slash_commands(self) -> list[str]:
        return [DIAGRAM_SLASH_COMMAND]

    def build_manifest(self, context: SkillContext) -> SkillManifest:
        return SkillManifest(
            name="diagram",
            slash_command=DIAGRAM_SLASH_COMMAND,
            description="Diagram generation and management skill",
            system_prompt_addition=(
                "---\n"
                "Active skill: /diagram\n"
                "You must decide diagram_type from user intent and call create_diagram.\n"
                "If diagram type is unclear, call confirm_diagram_type first and wait for approval.\n"
                "Allowed diagram_type values are the registered types in DiagramTypeRegistry.\n"
                "---"
            ),
            tools=self._build_tools(context),
            confirmation_required=frozenset(
                {
                    "confirm_diagram_type",
                    "update_diagram",
                    "delete_diagram",
                }
            ),
            force_first_tool_call=True,
        )

    def _build_tools(self, context: SkillContext) -> list[ToolDefinition]:
        notebook_id = context.notebook_id
        return [
            _build_list_diagrams_tool(self._service, notebook_id),
            _build_read_diagram_tool(self._service),
            _build_confirm_diagram_type_tool(),
            _build_create_diagram_tool(self._service, notebook_id),
            _build_update_diagram_tool(self._service),
            _build_delete_diagram_tool(self._service),
        ]
```

## 6 个 Agent 工具

### list_diagrams

列出当前 notebook 下的图表元数据，支持可选 `document_id` 过滤。

### read_diagram

读取指定图表内容，供“先读后改”场景使用。

### confirm_diagram_type（新增）

用于“用户意图不明确时”的类型确认卡片：

```python
def _build_confirm_diagram_type_tool() -> ToolDefinition:
    async def execute(args: dict) -> ToolCallResult:
        return ToolCallResult(
            content=f"Diagram type confirmed: {args.get('diagram_type')}",
            metadata={
                "diagram_type": args.get("diagram_type"),
                "title": args.get("title"),
            },
        )

    return ToolDefinition(
        name="confirm_diagram_type",
        description=(
            "Ask the user to confirm the diagram type and optional title before creation. "
            "Use this only when user intent does not clearly specify the type."
        ),
        parameters={
            "type": "object",
            "properties": {
                "diagram_type": {
                    "type": "string",
                    "description": "Proposed type, e.g. mindmap.",
                },
                "title": {
                    "type": "string",
                    "description": "Optional proposed title.",
                },
                "reason": {
                    "type": "string",
                    "description": "Why this type is proposed.",
                },
            },
            "required": ["diagram_type", "reason"],
        },
        execute=execute,
    )
```

> 该工具本身不写入数据库，主要用于触发 confirmation 流。

### create_diagram

与旧方案不同，`diagram_type` 不再由 slash 命令隐式绑定，而是由 Agent 显式传参：

```python
def _build_create_diagram_tool(service: DiagramService, notebook_id: str) -> ToolDefinition:
    async def execute(args: dict) -> ToolCallResult:
        try:
            diagram = await service.create_diagram(
                notebook_id=notebook_id,
                title=str(args["title"]),
                diagram_type=str(args["diagram_type"]),
                content=str(args["content"]),
                document_ids=list(args.get("document_ids") or []),
            )
            return ToolCallResult(
                content=f"Diagram created: {diagram.diagram_id}",
                metadata={"diagram_id": diagram.diagram_id},
            )
        except DiagramValidationError as exc:
            return ToolCallResult(content="", error=f"diagram validation failed: {exc}")
```

### update_diagram

更新图表内容。保留确认机制。

### delete_diagram

删除图表。保留确认机制。

## Slash 激活链路（单入口）

```
用户输入：
  /diagram 根据第三章内容画图

ChatService:
  SkillRegistry.match_command("/diagram ...")
  -> DiagramSkillProvider
  -> cleaned_message = "根据第三章内容画图"

Agent:
  1) 尝试从 prompt 判断 diagram_type
  2) 明确 -> create_diagram(diagram_type=..., ...)
  3) 不明确 -> confirm_diagram_type(...)（触发确认卡片）
     用户确认后再 create_diagram
```

## 确认机制范围

- `confirm_diagram_type`：当类型不明确时用于“创建前确认”
- `update_diagram`：内容覆盖更新前确认
- `delete_diagram`：删除前确认

统一使用：
- SSE 字段：`args_summary`
- 回调接口：`POST /api/v1/chat/{session_id}/confirm`
- 超时：180 秒

## 注册到 SkillRegistry

在应用 DI 初始化时，和 NoteSkillProvider 一样注册：

```python
registry.register(NoteSkillProvider(...))
registry.register(DiagramSkillProvider(diagram_service=diagram_service))
```
