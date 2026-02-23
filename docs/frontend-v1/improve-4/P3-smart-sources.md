# P3: 智能引用来源

## 问题描述

当前三种模式（Chat、Ask、Explain/Conclude）在消息生成后统一显示"引用来源"，但实际语义完全不同：

1. **Chat 模式**：`_collect_sources()` 是 agent 执行结束后单独发起的 pgvector top_k=3 查询，与本次回答无因果关系。用户提问"今天南京天气如何？"不调用任何工具，后端仍会补查并推送 sources，导致不相关的文档引用出现在回答下方。

2. **Ask 模式**：sources 来自 ReActAgent 的 hybrid retriever（pgvector + ES），是真实参与答案生成的检索结果，但无相关性分数过滤，低质量 chunk 也会出现。

3. **Explain/Conclude 模式**：sources 来自 `CondensePlusContextChatEngine` 的 `source_nodes`，是真实引用的文档片段，质量最高。

## 根因分析

```
Chat 模式当前 sources 路径：
  FunctionAgent 执行（ES 工具调用，影响答案）
    ↓ 执行完成
  _collect_sources(message)  ← 单独 pgvector top_k=3 补查
    ↓ 与答案无因果关系
  yield {"type": "sources", "sources": [...]}  ← 始终非空
```

核心问题：Chat 模式的 context 来自 ES 工具调用，但 sources 却是事后 pgvector 补查，两者来源不同。

## 设计方案

### 1. 后端：新增 sources_type 字段

在 SSE `sources` 事件中新增 `sources_type` 字段，前端据此选择展示方式：

```
sources_type 取值：
  "tool_results"  ← Chat 模式，ES 工具调用结果（有工具调用时才发此事件）
  "retrieval"     ← Ask/Explain/Conclude，真实检索引用（sources 非空时才发）
```

SSE 事件格式变更（向后兼容，新增字段）：

```
{"type": "sources", "sources": [...], "sources_type": "retrieval"}
```

> **"不显示"语义的统一处理**：后端不发 sources 事件（而非发一个 `sources_type: "none"` 的空事件）。前端仅需处理"收到 sources 事件"和"未收到 sources 事件"两种状态，逻辑更清晰，向后兼容性更好（旧版前端不处理该字段时也不会出错）。

### 2. 后端：Chat 模式 sources 逻辑调整

**代码现状（已确认）**：`chat_mode.py` 已有 `had_tool_calls = bool(getattr(self._runner, "had_tool_calls", False))` 判断（第 183 行），无需新增属性暴露。

**需要解决的关键问题**：ES 工具的 `_search()` 方法目前**只返回格式化字符串**（供 LLM 消费），不暴露结构化数据（`document_id`、`title`、`score`）。要将 ES 检索结果作为 `ToolResultsCard` 的来源，必须从工具实例获取结构化的原始结果。

**方案**：在 `ElasticsearchSearchTool` 上新增 `_last_raw_results` 侧通道属性，每次 `_search()` 调用后同时保存结构化结果；`ChatMode` 持有工具实例引用，在 agent 执行完成后读取此属性。

```python
# es_search_tool.py - ElasticsearchSearchTool 新增侧通道
class ElasticsearchSearchTool:
    def __init__(self, ...):
        ...
        self._last_raw_results: List[dict] = []  # 新增

    def _search(self, query: str) -> str:
        """Internal search method — returns formatted string for LLM,
        and also stores structured results in _last_raw_results."""
        raw_results, formatted = _es_search_with_raw(...)
        self._last_raw_results = raw_results  # 同步保存
        return formatted
```

`_es_search_with_raw()` 是对现有 `_es_search()` 的最小改造：在返回格式化字符串的同时，也返回原始 hits 列表，每条格式：

```python
{
    "document_id": str,   # 来自 _extract_hit_document_id()
    "title": str,
    "score": float,
    "text": str,          # 截断至 500 字符（与现有一致）
    "chunk_id": "",       # ES 不含 chunk_id，留空（前端不跳转，此字段不强制）
}
```

**ChatMode 中的调整逻辑**：

```
_stream() 执行完毕后：
  if had_tool_calls:
      raw = es_tool_instance._last_raw_results  ← 从工具实例取结构化数据
      self._last_sources = raw
      # → chat_service 后续以 sources_type="tool_results" 发出事件
  else:
      self._last_sources = []   ← 无工具调用，不补查 pgvector，不发 sources 事件
```

移除 `_collect_sources()` 的调用（或保留方法但不在 _stream 路径中调用），彻底去除事后 pgvector 补查。

> **`had_tool_calls` 依赖澄清**：此属性已存在于 `chat_mode.py` 第 183 行，P3 无需等待 P4 完成，两个任务完全独立，可并行推进。

### 3. 后端：Ask 模式 sources 过滤

在 `chat_service.py` 的 `_filter_valid_sources()` 后，追加相关性分数过滤：

- 保留 `score >= 0.3` 的 sources（阈值可通过配置项调整）
- 过滤后若 sources 为空，设置 `sources_type: "none"`，不发 sources 事件

此过滤在 `chat_service.py` 层完成，对各 Mode 透明。

### 4. 前端：SseEvent 类型扩展

在 `frontend/src/lib/api/types.ts` 的 `SseEvent` 联合类型中：

```
SourcesEvent 类型新增字段：
  sources_type?: "tool_results" | "retrieval" | "none"
```

`ChatMessage` store 中同步新增 `sourcesType` 字段，在收到 sources 事件时一并存储。

### 5. 前端：组件拆分

将现有 `SourcesCard` 拆分，在 `message-item.tsx` 中根据 `message.sourcesType` 分发：

#### ToolResultsCard（Chat 模式，sources_type = "tool_results"）

展示 ES 工具调用命中的文档片段：

```
工具调用结果
─────────────────────────────────
[1] document-title.pdf
    检索到的文本摘要（1 行，截断 80 字符）
[2] another-doc.md
    ...
```

- 标题文字：`工具调用结果`（通过 P2 i18n：`uiStrings.sources.toolResults`）
- 卡片样式：更低饱和度，字号 11px，较现有 SourcesCard 更紧凑
- 不提供点击跳转（工具结果不对应精确 chunk，跳转意义不大）
- 最多显示 3 条，无"展开更多"

#### DocumentReferencesCard（Ask/Explain/Conclude，sources_type = "retrieval"）

即现有 `SourcesCard` 的精化版：

- 标题文字：`引用来源`
- 可点击跳转文档（保持现有 `onOpenDocument` 行为）
- 最多显示 3 条，超出显示"展开更多（共 N 条）"
- 展开后列表最大高度 240px，内部滚动

#### 条件渲染逻辑（message-item.tsx）

```
if (!message.sources || message.sources.length === 0) → 不渲染
else if (message.sourcesType === "tool_results")       → <ToolResultsCard />
else                                                    → <DocumentReferencesCard />
```

## 涉及文件

| 文件 | 修改内容 |
|------|----------|
| `newbee_notebook/core/tools/es_search_tool.py` | `ElasticsearchSearchTool` 新增 `_last_raw_results` 侧通道；`_es_search_with_raw()` 改造返回结构化数据 |
| `newbee_notebook/core/engine/modes/chat_mode.py` | `_stream()` 中有工具调用时从 `es_tool._last_raw_results` 取 sources；无工具调用时 `_last_sources = []`；移除事后 pgvector 补查 |
| `newbee_notebook/application/services/chat_service.py` | sources 事件新增 `sources_type` 字段（`"tool_results"` / `"retrieval"`）；sources 为空时不发 sources 事件；Ask 模式追加 score 阈值过滤 |
| `frontend/src/lib/api/types.ts` | `SourcesEvent` 新增 `sources_type?: "tool_results" \| "retrieval"` 字段 |
| `frontend/src/stores/chat-store.ts` | `ChatMessage` 新增 `sourcesType` 字段 |
| `frontend/src/components/chat/sources-card.tsx` | 重命名为 `DocumentReferencesCard`；新增 `ToolResultsCard` |
| `frontend/src/components/chat/message-item.tsx` | 按 `sourcesType` 分发组件 |
| `frontend/src/lib/i18n/strings.ts` | 新增 `sources.toolResults` 文本（与 P2 同步） |

> **ExplainCard 文本迁移 vs 结构改动分离**：`explain-card.tsx` 的 i18n 文本迁移在批次 B（P2 阶段）完成；sources 展示结构调整在批次 D（P3 阶段）完成，两次改动不重叠且不冲突。

## 验证标准

- Chat 模式，无工具调用（纯 LLM 回答）：消息下方无任何引用 UI
- Chat 模式，ES 工具调用触发：显示"工具调用结果"卡片，内容来自 ES 检索结果
- Ask 模式，检索有相关结果（score >= 0.3）：显示"引用来源"卡片，可点击跳转
- Ask 模式，检索结果全部 score < 0.3：消息下方无任何引用 UI
- Explain/Conclude 模式：显示"引用来源"卡片，行为与当前一致
- SSE `sources_type` 字段向后兼容：未传该字段时前端默认按 `"retrieval"` 处理

## 测试补充与现状（2026-02-23）

### 已验证通过

- Chat 模式（纯 LLM 回复）：不再出现无关引用 UI（不发 `sources` 事件）
- Chat 模式（天气工具场景）：`<tool_call>` 泄漏已消失（P4 两阶段流式回归通过）
- 协议兼容：前端对缺省 `sources_type` 仍按 `"retrieval"` 处理

### 当前环境中的未完全验证项

- `ToolResultsCard`（非空命中）未稳定复现：
  - 当前 notebook 环境下多次显式 `knowledge_base_search` 查询返回空结果或模型未给出命中 sources
  - 因此未完成“带真实 ES 命中数据的 ToolResultsCard UI 展示”验证

### 已追加的兼容兜底（实现层）

- Ask 模式 score 过滤在“全部无有效正分数（0.0/缺失）”时不再清空 sources
- Ask 模式在 `document_id` 校验导致 sources 全部被清空时，允许返回展示用 sources（Reference 入库仍只保存有效 `document_id`）

> 仍需关注：若 `AskMode` 上游 `_last_sources` 本身为空（即 agent 成功回答但 mode 未保留 sources），上述兜底无法生效。该问题属于 AskMode sources 收集链路与 agent 实际检索链路的耦合问题，建议后续单独排查。
