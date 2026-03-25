# 引用来源卡片：问题分析

## 背景

Agent 和 Ask 模式在调用 `knowledge_base` 工具后，会在消息气泡下方展示"引用来源"卡片。该卡片的数据来源完全相同——均为 RAG 检索返回的 `SourceItem` 列表——但当前实现存在渲染路径分裂、来源语义判定错误、引用内容展示不完整三个问题。

---

## 涉及文件

| 文件 | 作用 |
|------|------|
| `newbee_notebook/application/services/chat_service.py` | `_resolve_sources_type` 方法决定 `sources_type` 的值 |
| `frontend/src/components/chat/sources-card.tsx` | `DocumentReferencesCard` 和 `ToolResultsCard` 两个渲染组件 |
| `frontend/src/components/chat/message-item.tsx` | 依据 `sourcesType` 分支选择渲染哪个组件 |
| `frontend/src/stores/chat-store.ts` | `ChatMessage` 类型中的 `sourcesType` 字段定义 |
| `frontend/src/lib/api/types.ts` | `SseEventSources.sources_type` 的类型枚举 |
| `frontend/src/lib/hooks/useChatSession.ts` | 非流式回退路径中对 `sourcesType` 的赋值逻辑 |
| `frontend/src/lib/i18n/strings.ts` | `sources.toolResults` 字段（待清理） |

---

## 问题一：Agent 与 Ask 模式渲染路径分裂

### 现象

同样是 `knowledge_base` 工具返回的文档引用，Agent 模式展示虚线边框的 `ToolResultsCard`，Ask 模式展示实线边框的 `DocumentReferencesCard`，视觉语义不一致。

### 根本原因

`chat_service.py` 第 679 行：

```python
@staticmethod
def _resolve_sources_type(mode_enum: ModeType) -> str:
    if normalize_runtime_mode(mode_enum) is ModeType.AGENT:
        return "tool_results"
    return "retrieval"
```

该方法以 **运行模式** 作为判断依据，而非 **来源类型**。Agent 模式被硬编码返回 `"tool_results"`，导致前端选择了设计上用于非文档类工具输出的 `ToolResultsCard`。

`message-item.tsx` 第 153 行的前端分支：

```tsx
{message.sourcesType === "tool_results" ? (
  <ToolResultsCard sources={message.sources} />
) : (
  <DocumentReferencesCard sources={message.sources} onOpenDocument={onOpenDocument} />
)}
```

`ToolResultsCard` 的设计意图是展示无法跳转的工具输出（如搜索引擎结果、MCP 工具输出等），但实际上它承接了所有来自 `knowledge_base` 工具的结果，这在语义上是错误的。

此外，`useChatSession.ts` 第 473 行的非流式回退路径同样以 mode 为判断依据：

```typescript
sourcesType: mode === "agent" ? "tool_results" : "retrieval",
```

### 结论

`sources_type` 字段的语义应描述**引用内容的来源类型**，而不是**当前对话模式**。实现上不应采用恒定字符串，而应基于 `sources[].source_type` 动态判定：

- 全部为 `retrieval` 时返回 `document_retrieval`
- 出现非 `retrieval` 来源时返回 `tool_results`
- 空来源返回 `none`

---

## 问题二：卡片点击行为与阅读路径职责冲突

### 现象

点击 `DocumentReferencesCard` 条目会尝试打开文档，但实际无法定位到引用片段，造成"点击后没到引用处"的体验落差。

### 根本原因

点击回调仅传入 `document_id`：

```tsx
onClick={() => {
  if (!canOpen) return;
  onOpenDocument(source.document_id);
}}
```

`DocumentReferencesCard` 没有将 `chunk_id` 或 `source.text` 传递给导航层，阅读器无法知晓应滚动到哪个位置。尽管系统中存在基于 `markId` 的书签跳转机制，但 chunk 引用与书签是两套独立的数据结构，无法直接复用。

更重要的是，RAG 检索返回的 `chunk_id` 记录的是 LlamaIndex 节点 ID，阅读器的 chunk 渲染体系基于 Markdown 分段，两者之间没有稳定的映射关系，无法可靠地定位到文档中的对应位置。

### 结论

当前架构下，从 `chunk_id` 反向定位文档内位置不具备可靠性，且实现成本极高。更合理的交互是：**引用卡片内就地展示完整文本**。文档打开入口由左侧 Sources 面板统一提供，不在每条引用上增加额外"打开文档"入口。

---

## 问题三：引用内容展示过于简短

### 现象

`DocumentReferencesCard` 展示 `source.text.slice(0, 120)` 并以 2 行截断，`ToolResultsCard` 更只展示 80 字符单行省略。用户无法从卡片上判断该引用段落是否与问题相关，必须跳转文档才能读到完整内容。

### 根本原因

RAG 检索返回的 `text` 字段对应一个完整的文档 chunk，长度约为 512 token（约 300-1000 中文字符）。卡片设计的初衷是保持界面紧凑，因此主动截断了内容。但截断后的信息量过低，用户体验降级明显。

### 结论

需要在不破坏整体卡片布局的前提下提供查看完整引用内容的入口。展开方案应满足：

- 未点击时与当前视觉保持一致（紧凑布局）
- 点击某条引用后弹出展示完整文本的内联浮层
- 浮层不撑大引用卡片本体，不影响其他引用条目的可见性

---

## 不在本次修复范围内

- 从 chunk 引用跳转至文档内精确位置（依赖 chunk_id 与阅读器 chunk 的双向映射，需专项设计）
- ES 关键词检索返回的 `chunk_id` 为空字符串的问题（影响去重逻辑，属于检索层问题）
- 引用来源的评分可视化（`source.score` 字段目前未在前端展示）
