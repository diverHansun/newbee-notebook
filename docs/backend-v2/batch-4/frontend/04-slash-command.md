# Slash 命令集成

## 概述

batch-4 图表功能采用单入口命令：`/diagram`。  
这比按类型拆分多个命令（`/mindmap`、`/flowchart`、`/sequence`）更易上手，用户只需记住一个命令。

slash 命令选择器 UI 继续复用 batch-3 的组件与交互模型。

## 命令条目

在现有命令列表中新增：

```typescript
{
  command: "/diagram",
  description: t(uiStrings.slashCommand.diagramDescription),
  available: true,
}
```

> 说明：当前前端已有 `uiStrings.slashCommand` 命名空间（单数），batch-4 延续该结构。

## 用户交互语义

### 场景 A：用户明确类型

示例：

- `/diagram 根据第三章生成思维导图`
- `/diagram draw a flowchart for the ingestion pipeline`

后端 Agent 在 prompt 中识别到明确类型后，直接创建对应图表。

### 场景 B：用户未明确类型

示例：

- `/diagram 把这章内容可视化一下`
- `/diagram summarize relationships in a graph`

后端 Agent 先触发 `confirmation_request`（`confirm_diagram_type` 工具），前端展示确认卡片：

- 建议类型（例如 mindmap）
- 简短原因（为什么建议该类型）

用户确认后继续创建；拒绝后 Agent 重新询问或调整类型。

## 选择器行为（复用 batch-3）

- 用户输入 `/` 后显示命令面板
- 前缀过滤（输入 `/d` 可过滤到 `/diagram`）
- 选中后自动补全为 `/diagram `
- 命令发送后由后端 SkillRegistry 激活 diagram skill

## 文档范围（source documents）联动

`/diagram` 与现有文档范围选择器联动逻辑不变：

- UI 选择了特定文档：后端收到 `selected_document_ids`，优先限定检索范围
- UI 选择全部文档：Agent 按用户 prompt 决定范围

前端只需继续传递 `source_document_ids`。

## 图表列表自动刷新

图表创建/更新后列表刷新的触发策略：

- 在 SSE `done` 后判断“本次消息是否 diagram skill 请求”
- 是则 invalidate `["diagrams", notebookId]`

由于当前 SSE 事件体不直接提供 `active_skill` 字段，前端应在请求发送时记录命令上下文（是否以 `/diagram` 开头），在 `done` 阶段据此刷新。
