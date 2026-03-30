# Frontend-v2 改进计划 5 - 移除 RAG 可用性预判与后端模式守卫修正

## 概述

本文档集描述 Newbee Notebook 第五轮前端改进：移除前端对 RAG 可用性的预判逻辑，同步修正后端对 Ask 模式的 409 阻断，使聊天模式的可用性不再受文档处理状态影响。

## 背景

当前系统在文档处理期间会完全禁用 Ask 模式（前端禁用发送按钮 + 显示"RAG 不可用"标识），但这与实际业务逻辑不符：

1. **已完成的文档不受影响** - knowledge_base 工具可以正常检索所有已完成索引的文档，新上传的文档处理不影响已有文档的使用
2. **前端预判过于激进** - 前端以"是否存在任何处理中文档"一刀切禁用，而后端实际上在"存在已完成文档"时允许 Ask 请求通过
3. **文档选择器已自然过滤** - 未处理完成的文档在来源选择器中本身就不可见，用户无法选中未就绪的文档
4. **Agent 模式不依赖 RAG** - Agent 模式可以在任何文档状态下正常工作，当前的"可先使用 Agent 模式"提示是多余的

## 问题定位

### 前端问题

`notebook-workspace.tsx` 中 `buildRagHint()` 函数的判断逻辑：只要有任何一个文档处于 `uploaded`、`pending`、`processing`、`converted` 状态，就生成 ragHint 字符串，导致 `askBlocked = true`，进而：

- 黄色警告 banner 显示"文档处理中，RAG 暂不可用"
- Ask 模式发送按钮被禁用
- 红色 badge 显示"RAG 不可用"

### 后端问题

`chat_service.py` 的 `_validate_mode_guard()` 方法将 Ask 归入 `rag_modes` 元组，当 0 个已完成文档且存在处理中文档时返回 HTTP 409 错误。Ask 模式应当和 Agent 一样始终放行，由 LLM 在回复中自然处理无检索结果的情况。

## 设计目标

- Ask 和 Agent 模式在任何文档状态下都可正常发送消息
- 后端不再对 Ask/Agent 模式返回 409 文档处理错误
- Explain 和 Conclude 模式保留现有的 409 守卫（这两个模式在 Markdown 阅读器中交互，文档未就绪时无法打开阅读器）
- 移除前端所有与 RAG 可用性预判相关的 UI 元素和逻辑
- 文档状态轮询和 Sources 面板的状态展示保持不变

## 文档结构

| 文档 | 职责 |
|------|------|
| README.md | 本文档，概述、背景与问题定位 |
| 01-problem-analysis.md | 现有代码的详细分析，包含完整的数据流和受影响代码清单 |
| 02-design-spec.md | 具体的变更规范，分前端和后端两部分 |
| 03-implementation-plan.md | 实现步骤、文件修改清单与测试计划 |

## 变更范围

| 层级 | 变更类型 | 说明 |
|------|---------|------|
| 前端 notebook-workspace.tsx | 删除代码 | 移除 `buildRagHint` 函数、`ragHint`/`askBlocked` 变量及 props 传递 |
| 前端 chat-panel.tsx | 删除代码 | 移除 `askBlocked`/`ragHint` props、黄色警告 banner |
| 前端 chat-input.tsx | 删除代码 | 移除 `askBlocked` prop、发送按钮禁用逻辑、红色 badge |
| 前端 strings.ts | 删除条目 | 移除 `ragUnavailable` 和 `ragHint` 两条 i18n 字符串 |
| 前端测试文件 | 修改 | 更新涉及 `askBlocked` 的测试用例 |
| 后端 chat_service.py | 修改逻辑 | `_validate_mode_guard` 中将 Ask 从 `rag_modes` 守卫中排除 |
| 后端 chat_service.py | 修改逻辑 | 非流式路径增加与流式路径一致的 CHAT/AGENT/ASK 跳过守卫判断 |
| 后端测试文件 | 修改 | 更新 `_validate_mode_guard` 相关测试 |

## 设计原则

- **信任后端边界** - 前端不预判模式可用性，由后端在真正需要时（Explain/Conclude 针对未就绪文档）返回错误
- **保持文档状态展示** - Sources 面板的文档处理进度展示不受影响，用户仍可看到每个文档的处理状态
- **最小改动** - 以删除代码为主，不引入新的状态管理或 UI 元素
