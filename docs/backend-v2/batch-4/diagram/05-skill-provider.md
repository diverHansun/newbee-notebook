# Skill 集成

## 前置条件

本文档描述的 DiagramSkillProvider 依赖 batch-3 note-related-skills 提供的以下基础设施：

- `SkillProvider` ABC
- `SkillManifest` 数据类
- `SkillContext` 数据类
- `SkillRegistry`（含 `match_command` 方法）
- `ConfirmationGateway`（AgentLoop 确认暂停机制）
- `ConfirmationRequestEvent`（stream_events.py 中新增的事件类型）
- ChatService 中的 slash 命令检测与工具注入逻辑

以上组件在 batch-3 实现，batch-4 直接复用，不重新实现。

对齐说明：

- `SkillContext` 采用 batch-3 收敛后的字段：`notebook_id`、`activated_command`、`selected_document_ids`
- Diagram skill 的确认事件摘要字段统一为 `args_summary`
- 用户确认接口统一为 `POST /api/v1/chat/{session_id}/confirm`

## DiagramSkillProvider

```python
class DiagramSkillProvider(SkillProvider):
    """
    为所有已注册图表类型提供 Skill 工具。
    一个 Provider 实例处理所有图表类型的 slash 命令，
    通过 SkillContext.activated_command 区分当前激活的类型。
    """

    def __init__(self, diagram_service: DiagramService) -> None:
        self._service = diagram_service

    @property
    def skill_name(self) -> str:
        return "diagram"

    @property
    def slash_commands(self) -> list[str]:
        """返回所有已注册图表类型的 slash 命令，由 SkillRegistry 用于命令匹配。"""
        return get_all_slash_commands()
        # batch-4 返回：["/mindmap"]

    def build_manifest(self, context: SkillContext) -> SkillManifest:
        """
        根据激活的 slash 命令构建 SkillManifest。

        context.activated_command 示例："/mindmap"
        从注册表取 descriptor，获取：
        - system_prompt_addition：注入 AgentLoop 的生成指令
        - validator：用于 create/update 工具的格式校验
        """
        diagram_type = context.activated_command.lstrip("/")
        descriptor = get_descriptor(diagram_type)

        return SkillManifest(
            name=f"diagram:{diagram_type}",
            slash_command=descriptor.slash_command,
            description=descriptor.description,
            system_prompt_addition=descriptor.agent_system_prompt,
            tools=self._build_tools(context, diagram_type),
            confirmation_required=frozenset({"update_diagram", "delete_diagram"}),
        )

    def _build_tools(
        self,
        context: SkillContext,
        diagram_type: str,
    ) -> list[ToolDefinition]:
        notebook_id = context.notebook_id
        return [
            _build_list_diagrams_tool(self._service, notebook_id),
            _build_read_diagram_tool(self._service),
            _build_create_diagram_tool(self._service, notebook_id, diagram_type),
            _build_update_diagram_tool(self._service),
            _build_delete_diagram_tool(self._service),
        ]
```

## 5 个 Agent 工具

### list_diagrams

```python
def _build_list_diagrams_tool(
    service: DiagramService,
    notebook_id: str,
) -> ToolDefinition:
    async def execute(args: dict) -> ToolCallResult:
        document_id = args.get("document_id")
        diagrams = await service.list_diagrams(notebook_id, document_id=document_id)
        items = [
            {
                "diagram_id": d.diagram_id,
                "title": d.title,
                "diagram_type": d.diagram_type,
                "document_ids": d.document_ids,
                "created_at": d.created_at.isoformat(),
            }
            for d in diagrams
        ]
        return ToolCallResult(content=json.dumps(items, ensure_ascii=False))

    return ToolDefinition(
        name="list_diagrams",
        description="列出当前 notebook 中已创建的图表（元数据，不含内容）。可按关联文档过滤。",
        parameters={
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "可选。按关联文档 ID 过滤，不传则返回 notebook 下全部图表。",
                }
            },
            "required": [],
        },
        execute=execute,
    )
```

### read_diagram

```python
def _build_read_diagram_tool(service: DiagramService) -> ToolDefinition:
    async def execute(args: dict) -> ToolCallResult:
        diagram_id = args["diagram_id"]
        try:
            content = await service.get_diagram_content(diagram_id)
            diagram = await service.get_diagram(diagram_id)
            return ToolCallResult(
                content=content,
                metadata={"diagram_type": diagram.diagram_type, "format": diagram.format},
            )
        except DiagramNotFoundError:
            return ToolCallResult(content="", error=f"图表 {diagram_id} 不存在")

    return ToolDefinition(
        name="read_diagram",
        description="读取指定图表的完整内容（JSON 或 Mermaid 语法）。修改前应先读取现有内容。",
        parameters={
            "type": "object",
            "properties": {
                "diagram_id": {"type": "string", "description": "图表 ID"},
            },
            "required": ["diagram_id"],
        },
        execute=execute,
    )
```

### create_diagram

```python
def _build_create_diagram_tool(
    service: DiagramService,
    notebook_id: str,
    diagram_type: str,
) -> ToolDefinition:
    async def execute(args: dict) -> ToolCallResult:
        try:
            diagram = await service.create_diagram(
                notebook_id=notebook_id,
                title=args["title"],
                diagram_type=diagram_type,
                content=args["content"],
                document_ids=args.get("document_ids", []),
            )
            return ToolCallResult(
                content=f"图表已创建，diagram_id: {diagram.diagram_id}",
                metadata={"diagram_id": diagram.diagram_id},
            )
        except DiagramValidationError as e:
            return ToolCallResult(content="", error=f"图表格式校验失败：{e}")

    return ToolDefinition(
        name="create_diagram",
        description=(
            "创建新图表。content 必须严格符合格式要求，"
            "格式错误会返回具体错误信息，请根据错误修正后重试（最多 3 次）。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "图表标题，应简洁描述图表主题",
                },
                "content": {
                    "type": "string",
                    "description": "图表内容，reactflow_json 格式的 JSON 字符串",
                },
                "document_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "关联的文档 ID 列表，对应本次图表涉及的文档范围",
                },
            },
            "required": ["title", "content", "document_ids"],
        },
        execute=execute,
    )
```

### update_diagram

```python
def _build_update_diagram_tool(service: DiagramService) -> ToolDefinition:
    async def execute(args: dict) -> ToolCallResult:
        # 此工具在 SkillManifest.confirmation_required 中，
        # 执行前 AgentLoop 会暂停并发出 ConfirmationRequestEvent，
        # 用户确认后才会调用此 execute 函数。
        try:
            diagram = await service.update_diagram_content(
                diagram_id=args["diagram_id"],
                content=args["content"],
                title=args.get("title"),
            )
            return ToolCallResult(
                content=f"图表已更新，diagram_id: {diagram.diagram_id}",
                metadata={"diagram_id": diagram.diagram_id},
            )
        except DiagramNotFoundError:
            return ToolCallResult(content="", error=f"图表 {args['diagram_id']} 不存在")
        except DiagramValidationError as e:
            return ToolCallResult(content="", error=f"图表格式校验失败：{e}")

    return ToolDefinition(
        name="update_diagram",
        description=(
            "更新已有图表的内容。此操作会覆盖原图表，需要用户确认后执行。"
            "调用前应先使用 read_diagram 读取现有内容，"
            "在此基础上生成修改后的完整内容（非增量 patch）。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "diagram_id": {"type": "string", "description": "要更新的图表 ID"},
                "content": {
                    "type": "string",
                    "description": "完整的新内容（包含所有节点和边，不是增量修改）",
                },
                "title": {
                    "type": "string",
                    "description": "可选，更新图表标题",
                },
            },
            "required": ["diagram_id", "content"],
        },
        execute=execute,
    )
```

### delete_diagram

```python
def _build_delete_diagram_tool(service: DiagramService) -> ToolDefinition:
    async def execute(args: dict) -> ToolCallResult:
        # 同 update_diagram，执行前已经过用户确认。
        try:
            await service.delete_diagram(args["diagram_id"])
            return ToolCallResult(content=f"图表 {args['diagram_id']} 已删除")
        except DiagramNotFoundError:
            return ToolCallResult(content="", error=f"图表 {args['diagram_id']} 不存在")

    return ToolDefinition(
        name="delete_diagram",
        description="删除图表。此操作不可撤销，需要用户确认后执行。",
        parameters={
            "type": "object",
            "properties": {
                "diagram_id": {"type": "string", "description": "要删除的图表 ID"},
            },
            "required": ["diagram_id"],
        },
        execute=execute,
    )
```

## 注册到 SkillRegistry

在应用启动时，将 DiagramSkillProvider 注册到 SkillRegistry：

```python
# 应用初始化（依赖注入配置）
diagram_service = DiagramService(
    repository=PostgresDiagramRepository(db),
    storage=storage_service,
)
diagram_skill_provider = DiagramSkillProvider(diagram_service)
skill_registry.register(diagram_skill_provider)
```

## Slash 命令激活完整链路

```
用户在 chat 输入框输入：
  "/mindmap 根据大模型基础这本书的第三章画知识导图"
  （document scope：大模型基础.pdf）

ChatService.chat_stream() 检测到 "/" 前缀
  → SkillRegistry.match_command("/mindmap")
  → 返回 DiagramSkillProvider

ChatService 构建 SkillContext：
  SkillContext(
      notebook_id="...",
      activated_command="/mindmap",
      selected_document_ids=["doc-abc"],
  )

DiagramSkillProvider.build_manifest(context)
  → 取 DIAGRAM_TYPE_REGISTRY["mindmap"].agent_system_prompt
  → 构建 5 个工具（notebook_id、diagram_type 通过闭包注入）
  → 返回 SkillManifest

清洗消息：去掉 "/mindmap "
  → 传给 AgentLoop 的消息："根据大模型基础这本书的第三章画知识导图"

SessionManager._build_loop() 调用：
  ToolRegistry.get_tools("agent", external_tools=manifest.tools)
  → 内置工具 + 5 个 diagram 工具

AgentLoop 执行：
  system prompt 包含 agent_system_prompt 补充指令
  → Agent 调用 RAG 检索相关内容
  → Agent 生成 JSON 并调用 create_diagram
  → DiagramService 校验、存储
  → 返回 diagram_id 给 Agent
  → Agent 在回复中告知用户图表已生成
```

## 确认机制（update_diagram / delete_diagram）

复用 batch-3 ConfirmationGateway，流程与 Note 操作一致：

1. AgentLoop 检测到工具名在 `confirmation_required` 集合中
2. 暂停执行，yield `ConfirmationRequestEvent`（含 request_id、tool_name、args_summary）
3. 前端收到 SSE 事件，在消息流中渲染内联确认卡片
4. 用户点击确认或取消，前端调用 `POST /api/v1/chat/{session_id}/confirm`
5. ConfirmationGateway 释放 asyncio.Event，AgentLoop 恢复执行
6. 若用户取消，tool.execute() 不被调用，AgentLoop 将"用户已取消"追加到上下文

超时时间：180 秒（3 分钟），与 batch-3 note skill 确认机制一致。
