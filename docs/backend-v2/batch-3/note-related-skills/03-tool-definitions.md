# Note-Related-Skills 模块：Agent 工具定义

## 1. 定位

本文档定义 `/note` skill 激活后注入给 agent 的 ToolDefinition 列表。每个工具遵循 batch-2 建立的统一工具契约（ToolDefinition + ToolCallResult）。

## 2. 工具总览

| 工具名称 | 操作类型 | 需要确认 | 说明 |
|---------|---------|---------|------|
| list_notes | 读 | 否 | 查询当前 notebook 下的笔记列表 |
| read_note | 读 | 否 | 读取笔记内容和引用的书签 |
| create_note | 写 | 否 | 创建笔记并关联文档 |
| update_note | 写 | 是 | 更新笔记标题或内容 |
| delete_note | 写 | 是 | 删除笔记 |
| list_marks | 读 | 否 | 查询书签列表 |
| associate_note_document | 写 | 否 | 将笔记与文档关联 |
| disassociate_note_document | 写 | 是 | 解除笔记与文档的关联 |

## 3. 工具详细定义

### 3.1 list_notes

查询当前 notebook 下的笔记列表。

```python
ToolDefinition(
    name="list_notes",
    description="查询当前笔记本中的笔记列表。可按文档过滤。返回笔记标题、关联文档和更新时间。",
    parameters={
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "可选。按指定文档过滤笔记。"
            }
        },
        "required": []
    },
    execute=...
)
```

返回示例：

```
找到 3 条笔记：
1. [笔记标题A] - 关联文档：大模型基础.pdf - 更新于 2026-03-17
2. [笔记标题B] - 关联文档：数据科学教材.xlsx - 更新于 2026-03-16
3. [笔记标题C] - 关联文档：大模型基础.pdf, 数据科学教材.xlsx - 更新于 2026-03-15
```

实现要点：notebook_id 在构建工具时通过闭包从 SkillContext 注入，agent 无需感知。

### 3.2 read_note

读取指定笔记的完整内容和引用的书签信息。

```python
ToolDefinition(
    name="read_note",
    description="读取指定笔记的完整内容，包括 Markdown 文本和引用的书签列表。",
    parameters={
        "type": "object",
        "properties": {
            "note_id": {
                "type": "string",
                "description": "笔记 ID"
            }
        },
        "required": ["note_id"]
    },
    execute=...
)
```

返回内容包含：
- 笔记标题
- Markdown 文本内容
- 关联文档列表（document_id + title）
- 引用的书签列表（mark_id + anchor_text + document_title）

### 3.3 create_note

创建新笔记，可同时关联文档和写入初始内容。

```python
ToolDefinition(
    name="create_note",
    description="创建一条新笔记。可指定标题、初始内容和关联的文档。",
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "笔记标题"
            },
            "content": {
                "type": "string",
                "description": "可选。Markdown 格式的初始内容。"
            },
            "document_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "可选。关联的文档 ID 列表。"
            }
        },
        "required": ["title"]
    },
    execute=...
)
```

### 3.4 update_note

更新笔记标题或内容。需要用户确认。

```python
ToolDefinition(
    name="update_note",
    description="更新指定笔记的标题或内容。此操作需要用户确认。",
    parameters={
        "type": "object",
        "properties": {
            "note_id": {
                "type": "string",
                "description": "笔记 ID"
            },
            "title": {
                "type": "string",
                "description": "可选。新标题。"
            },
            "content": {
                "type": "string",
                "description": "可选。新的 Markdown 内容。"
            }
        },
        "required": ["note_id"]
    },
    execute=...
)
```

### 3.5 delete_note

删除指定笔记。需要用户确认。

```python
ToolDefinition(
    name="delete_note",
    description="删除指定笔记。关联的文档标签和书签引用会一并清除。此操作需要用户确认。",
    parameters={
        "type": "object",
        "properties": {
            "note_id": {
                "type": "string",
                "description": "笔记 ID"
            }
        },
        "required": ["note_id"]
    },
    execute=...
)
```

### 3.6 list_marks

查询书签列表。只读，不支持创建。

```python
ToolDefinition(
    name="list_marks",
    description="查询书签列表。可按文档过滤，返回书签的标记文本、所属文档和位置信息。",
    parameters={
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "可选。按指定文档过滤书签。不指定则返回当前笔记本下所有文档的书签。"
            }
        },
        "required": []
    },
    execute=...
)
```

返回示例：

```
找到 5 个书签：
1. "大模型的训练过程分为预训练和微调两个阶段" - 来自《大模型基础》
2. "Transformer 架构由编码器和解码器组成" - 来自《大模型基础》
3. ...
```

实现要点：不指定 document_id 时，通过 MarkService.list_by_notebook(notebook_id) 查询。notebook_id 从 SkillContext 注入。

### 3.7 associate_note_document

将笔记与文档建立关联。

```python
ToolDefinition(
    name="associate_note_document",
    description="将笔记与指定文档关联，表示该笔记与此文档相关。",
    parameters={
        "type": "object",
        "properties": {
            "note_id": {
                "type": "string",
                "description": "笔记 ID"
            },
            "document_id": {
                "type": "string",
                "description": "要关联的文档 ID"
            }
        },
        "required": ["note_id", "document_id"]
    },
    execute=...
)
```

### 3.8 disassociate_note_document

解除笔记与文档的关联。需要用户确认。

```python
ToolDefinition(
    name="disassociate_note_document",
    description="解除笔记与指定文档的关联。此操作需要用户确认。",
    parameters={
        "type": "object",
        "properties": {
            "note_id": {
                "type": "string",
                "description": "笔记 ID"
            },
            "document_id": {
                "type": "string",
                "description": "要解除关联的文档 ID"
            }
        },
        "required": ["note_id", "document_id"]
    },
    execute=...
)
```

## 4. 工具执行上下文注入

所有工具的 execute 函数通过闭包捕获 SkillContext 中的 notebook_id。agent 的工具参数中不需要 notebook_id 字段。

```python
def _build_list_notes_tool(self, context: SkillContext) -> ToolDefinition:
    async def execute(args: dict) -> ToolCallResult:
        document_id = args.get("document_id")
        notes = await self._note_service.list_by_notebook(
            notebook_id=context.notebook_id,
            document_id=document_id,
        )
        content = self._format_notes_list(notes)
        return ToolCallResult(content=content)

    return ToolDefinition(
        name="list_notes",
        description="...",
        parameters={...},
        execute=execute,
    )
```

## 5. ToolCallResult 格式

所有工具返回纯文本格式的 ToolCallResult.content。不返回 JSON，因为 agent 需要直接理解内容并组织回复。

| 工具 | content 格式 |
|------|-------------|
| list_notes | 编号列表，包含标题、关联文档、更新时间 |
| read_note | 标题 + 完整 Markdown 内容 + 关联文档列表 + 书签引用列表 |
| create_note | "笔记已创建：[标题]，ID: xxx" |
| update_note | "笔记已更新：[标题]" |
| delete_note | "笔记已删除：[标题]" |
| list_marks | 编号列表，包含标记文本、所属文档 |
| associate_note_document | "已将笔记 [标题] 与文档 [文档名] 关联" |
| disassociate_note_document | "已解除笔记 [标题] 与文档 [文档名] 的关联" |

错误时设置 ToolCallResult.error 字段，content 中包含人类可读的错误描述。
