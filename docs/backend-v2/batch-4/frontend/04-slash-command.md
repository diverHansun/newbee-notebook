# Slash 命令集成

## 概述

图表功能通过 slash 命令触发 Agent 生成，与 batch-3 设计的 slash 命令选择器共用同一套 UI 组件和激活逻辑，batch-4 只需新增命令条目，无需修改选择器组件本身。

slash 命令选择器的完整设计见 `docs/backend-v2/batch-3/frontend/03-skill-frontend.md`，本文档仅描述 batch-4 新增的图表相关命令条目。

## 新增命令条目

在现有的 slash 命令注册表中新增以下条目（batch-4 注册，结构与 batch-3 /note 一致）：

```typescript
// 与 batch-3 的 /note 条目并列
{
  command: "/mindmap",
  label: t(uiStrings.slashCommands.mindmap.label),
  description: t(uiStrings.slashCommands.mindmap.description),
  available: true,
},

// 预留条目（未来 batch 注册时设置 available: true）
{
  command: "/flowchart",
  label: t(uiStrings.slashCommands.flowchart.label),
  description: t(uiStrings.slashCommands.flowchart.description),
  available: false,   // 显示为"即将推出"
},
{
  command: "/sequence",
  label: t(uiStrings.slashCommands.sequence.label),
  description: t(uiStrings.slashCommands.sequence.description),
  available: false,
},
```

## Slash 命令选择器 UI 行为（复用 batch-3）

用户在聊天输入框键入 "/" 时，输入框上方弹出命令选择器面板，列出所有已注册的 slash 命令：

```
┌────────────────────────────────────────┐
│ /note      管理笔记                    │
│ /mindmap   生成思维导图                │
│ /flowchart 生成流程图    (即将推出)    │
│ /sequence  生成时序图    (即将推出)    │
└────────────────────────────────────────┘
```

- 用户继续输入字符时，列表按前缀过滤（例如输入 "/min" 只显示 /mindmap）
- 用户点击或按 Enter 选中条目 → 命令填入输入框，光标移到命令之后，等待用户继续输入提示内容
- `available: false` 的条目显示灰色 + "即将推出"标签，点击无效
- Escape 关闭选择器

## 典型使用流程

```
1. 用户在聊天输入框键入 "/"
   → 选择器弹出，显示所有可用命令

2. 用户点击 "/mindmap" 或输入 "/mindmap " 后继续输入
   例："/mindmap 根据大模型基础第三章生成知识导图"

3. 用户发送消息
   → ChatService 检测到 "/mindmap" 前缀
   → DiagramSkillProvider 激活，tools 注入 AgentLoop
   → Agent 执行 RAG 检索 + 生成 JSON + 调用 create_diagram

4. 图表生成成功后：
   → Agent 在聊天回复中告知用户图表已创建，可在 Studio 图表面板查看
   → Studio 图表列表 TanStack Query 自动刷新（QueryKey invalidation）
```

## 文档范围选择与 Slash 命令的联动

用户发送 `/mindmap` 时，聊天输入框已有文档范围选择器（batch-2 已有 UI，见截图），document scope 的处理逻辑：

| 场景 | Agent 行为 |
|------|-----------|
| UI 选择了特定文档 | SkillContext.selected_document_ids 不为空，Agent 仅对这些文档执行 RAG 检索 |
| UI 选择"全部文档"，且用户 prompt 中提及文档名 | Agent 根据 prompt 识别目标文档后执行 RAG |
| UI 选择"全部文档"，且用户 prompt 未指定文档 | Agent 自行判断检索范围，可能跨多个文档 |

此逻辑在后端 DiagramSkillProvider 和 ChatService 的 SkillContext 构建阶段处理，前端只需正确将当前 selected_document_ids 附带在请求中（已有实现）。
