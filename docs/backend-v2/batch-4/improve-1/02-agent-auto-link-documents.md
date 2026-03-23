# improve-1: Agent 创建笔记时自动关联文档

## 背景

当前 Agent 在 `/note` 技能中创建笔记时，`create_note` 工具已支持 `document_ids` 参数，
但 system prompt 没有指导 Agent 主动推断并填入相关文档。导致 Agent 创建的笔记通常不带
文档关联，用户需要事后手动关联。

同时，用户可能会在对话中要求 Agent 将现有笔记关联到指定文档，现有的
`associate_note_document` / `disassociate_note_document` 工具已具备此能力，
但 system prompt 中也没有明确引导 Agent 在适当时机使用它们。

## 目标

1. Agent 创建笔记时，自动根据笔记内容判断涉及哪些 notebook 文档，并在 `create_note` 调用中填入 `document_ids`
2. 更新笔记时不自动重新推断文档关联（保持用户手动管理）
3. 用户明确要求时，Agent 调用工具执行关联或取消关联

## 方案：纯 Prompt 驱动

仅修改 `newbee_notebook/skills/note/provider.py` 中 `build_manifest()` 的 `system_prompt_addition`，
不新增工具、不修改 API、不引入额外参数传递。

### 现有 system prompt

位于 `newbee_notebook/skills/note/provider.py` 第 38-47 行：

```python
system_prompt_addition=(
    "---\n"
    "Active skill: /note\n"
    "Use the available note and mark tools for every note or mark lookup, creation, update, "
    "delete, and association change.\n"
    "Do not ask the user to confirm in plain text, and do not tell the user to perform note "
    "changes manually when the tools can do it.\n"
    "When the user requests an update, delete, or disassociation, call the corresponding tool "
    "directly. The runtime confirmation flow will request approval for protected actions.\n"
    "---"
),
```

### 修改后的 system prompt

在现有指令之后追加文档关联相关的指导段落：

```python
system_prompt_addition=(
    "---\n"
    "Active skill: /note\n"
    "Use the available note and mark tools for every note or mark lookup, creation, update, "
    "delete, and association change.\n"
    "Do not ask the user to confirm in plain text, and do not tell the user to perform note "
    "changes manually when the tools can do it.\n"
    "When the user requests an update, delete, or disassociation, call the corresponding tool "
    "directly. The runtime confirmation flow will request approval for protected actions.\n"
    "\n"
    "Document association guidelines:\n"
    "- When creating a note, analyse the note content to determine which notebook documents "
    "it references or derives from. Pass those document IDs in the document_ids parameter of "
    "create_note. If the conversation context or chat history contains information about which "
    "documents were used, use that to infer the correct document_ids.\n"
    "- If you cannot confidently determine the relevant documents, leave document_ids empty "
    "rather than guessing.\n"
    "- Do NOT re-infer or change document associations when updating a note. Document links "
    "during updates should only be changed when the user explicitly requests it.\n"
    "- When the user asks to link or unlink a document from a note, use "
    "associate_note_document or disassociate_note_document accordingly.\n"
    "---"
),
```

### 推断流程

Agent 在接收到创建笔记的指令后，按以下顺序工作：

```
用户要求创建笔记
  |
  v
Agent 分析笔记内容来源
  |
  +-- 对话上下文中有明确的文档引用 --> 提取 document_ids
  |
  +-- 需要确认当前 notebook 有哪些文档 --> 调用 list_notes 查看已有笔记的关联文档，
  |                                        或根据对话上下文中已有的文档信息判断
  |
  +-- 无法确定 --> document_ids 留空
  |
  v
调用 create_note(title, content, document_ids)
```

说明：Agent 不需要专门的"列出文档"工具。在 Agent 对话中，用户发送的消息经过 RAG 流程，
对话上下文中已包含相关文档的 ID 和名称信息。Agent 可以直接从上下文中提取。
如果需要进一步确认，`list_notes` 工具的输出中也包含已有笔记的关联文档 ID。

## 涉及文件

| 文件 | 改动类型 |
| --- | --- |
| `newbee_notebook/skills/note/provider.py` | 修改 `system_prompt_addition`，追加文档关联指导段落 |

## 不涉及的改动

- 不新增工具：现有 `create_note`（含 `document_ids` 参数）和 `associate_note_document` / `disassociate_note_document` 已满足需求
- 不修改 API 端点：`POST /notes`、`POST /notes/{id}/documents`、`DELETE /notes/{id}/documents/{doc_id}` 已存在
- 不引入 context 注入：避免增加 `build_manifest()` 的参数传递复杂性
- 不修改 `update_note` 行为：更新时不自动重新推断文档关联
