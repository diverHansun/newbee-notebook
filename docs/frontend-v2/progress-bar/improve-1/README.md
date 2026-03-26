# AI 消息生成进度指示器优化

## 问题描述

当前 AI 消息生成过程中，进度指示器仅显示粗粒度的阶段信息（如"AI 正在思考..."、"正在检索知识库..."），无法体现具体的工具调用过程。后端 `AgentLoop` 已经发出了 `ToolCallEvent` 和 `ToolResultEvent` 事件，SSE 适配器也已将这些事件传递到前端，但前端 `useChatSession.ts` 完全忽略了 `tool_call` 和 `tool_result` 两种 SSE 事件类型。

### 当前状态

```
用户发送消息
  -> 显示 "AI 正在思考..."
  -> (如果有知识库检索) 显示 "正在检索知识库..."
  -> 显示 "正在生成回答..."
  -> 消息内容开始渲染
```

所有工具调用（网络搜索、MCP 工具、Skill 工具等）对用户不可见，统一表现为"AI 正在思考..."的等待状态。

### 目标状态

```
用户发送消息
  -> 显示 "AI 正在思考..."              (无工具调用时的简单场景，保持不变)
  -> 显示具体工具调用步骤列表:            (有工具调用时)
       done  检索知识库
       running  搜索网络...
     ----shimmer bar----
  -> 步骤列表渐隐消失
  -> 消息内容开始渲染
```

---

## 设计决策摘要

| 决策项 | 结论 | 理由 |
|--------|------|------|
| 信息粒度 | 阶段级语义化（方案 B） | 不暴露技术细节，用户友好 |
| 标签映射位置 | 前端 | 复用现有 i18n 体系，后端零改动 |
| 与 thinkingStage 的关系 | 共存，互斥渲染 | 无工具调用时保持现有行为，零回归风险 |
| 耗时显示 | 不显示 | 避免过度设计 |
| 消失方式 | 立即消失（与现有 ThinkingIndicator 一致），CSS 预留 0.5s 渐隐动画供后续启用 |
| 后端改动 | 无 | 事件协议已满足需求 |

---

## 涉及文件

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `frontend/src/lib/api/types.ts` | 新增类型 | 添加 `SseEventToolCall`、`SseEventToolResult` |
| `frontend/src/stores/chat-store.ts` | 扩展 | `ChatMessage` 新增 `toolSteps` 字段，新增 2 个 action |
| `frontend/src/lib/hooks/useChatSession.ts` | 扩展 | `onEvent` 新增 `tool_call`、`tool_result` 处理分支 |
| `frontend/src/components/chat/message-item.tsx` | 修改 + 新增组件 | 新增 `ToolStepsIndicator`，修改渲染条件 |
| `frontend/src/lib/i18n/strings.ts` | 新增词条 | 添加 `tools.*` 工具标签 |
| `frontend/src/styles/thinking-indicator.css` | 新增样式 | 添加 `.tool-steps-*` 系列样式 |

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [design-spec.md](./design-spec.md) | 设计规格：数据结构、事件流、状态模型、渲染逻辑 |
| [implementation-guide.md](./implementation-guide.md) | 实施指南：按文件列出具体改动，含代码示例 |
| [css-style-spec.md](./css-style-spec.md) | 样式规格：CSS 类定义、动画规格、与现有样式的关系 |
