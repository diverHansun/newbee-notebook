# 引用来源卡片：实施方案

> 本文档对应分析文档：`docs/frontend-v2/sources-card/analysis.md`

## 目标

1. 统一 Agent 与 Ask 模式的引用来源渲染路径，消除 `ToolResultsCard` 与 `DocumentReferencesCard` 并存的分裂现象。
2. 将 `sources_type` 的语义从"对话模式"修正为"引用内容类型"，并基于来源动态判定，而非后端恒定字符串。
3. 移除引用条目中的文档跳转行为，改为点击条目后就地弹出完整引用内容的内联浮层（Popover）。

---

## 改动总览

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `newbee_notebook/application/services/chat_service.py` | 修改 | `_resolve_sources_type` 基于 `sources[].source_type` 动态返回 |
| `frontend/src/lib/api/types.ts` | 修改 | `sources_type` 枚举值精简 |
| `frontend/src/stores/chat-store.ts` | 修改 | `sourcesType` 字段类型精简 |
| `frontend/src/lib/hooks/useChatSession.ts` | 修改 | 非流式回退路径赋值修正 |
| `frontend/src/components/chat/sources-card.tsx` | 重构 | 删除 `ToolResultsCard`，重构 `DocumentReferencesCard` |
| `frontend/src/components/chat/message-item.tsx` | 修改 | 移除分支判断，统一渲染 |
| `frontend/src/lib/i18n/strings.ts` | 修改 | 清理 `toolResults` 字段 |

---

## 任务一：后端 — 动态 sources_type 语义

**文件**：`newbee_notebook/application/services/chat_service.py`，第 678-682 行

将 `_resolve_sources_type` 方法中对 mode 的判断去掉，改为基于来源动态判定：

```python
@staticmethod
def _resolve_sources_type(sources: List[dict]) -> str:
  if not sources:
    return "none"
  source_types = {str(item.get("source_type") or "").strip().lower() for item in sources if str(item.get("source_type") or "").strip()}
  if not source_types or source_types.issubset({"retrieval"}):
    return "document_retrieval"
  return "tool_results"
```

---

## 任务二：前端类型层 — 精简 sources_type 枚举

本项目尚未发布，不需要兼容旧值，直接移除废弃枚举项。

**文件**：`frontend/src/lib/api/types.ts`，第 279 行

```typescript
export type SseEventSources = {
  type: "sources";
  sources: RawSource[];
  sources_type?: "document_retrieval" | "tool_results" | "none";
};
```

**文件**：`frontend/src/stores/chat-store.ts`，第 27 行

```typescript
sourcesType?: "document_retrieval" | "tool_results" | "none";
```

**文件**：`frontend/src/lib/hooks/useChatSession.ts`，第 473 行（非流式回退路径）

移除 mode 判断，统一赋值：

```typescript
sourcesType: "document_retrieval",
```

第 537 行（流式路径）不变，继续使用后端返回值并提供 fallback：

```typescript
sourcesType: event.sources_type || "document_retrieval",
```

---

## 任务三：删除 ToolResultsCard

**文件**：`frontend/src/components/chat/sources-card.tsx`

删除第 14-16 行的 `ToolResultsCardProps` 类型定义和第 109-165 行的 `ToolResultsCard` 函数组件。

**文件**：`frontend/src/components/chat/message-item.tsx`，第 7 行

从 import 语句中移除 `ToolResultsCard`：

```typescript
import { DocumentReferencesCard } from "@/components/chat/sources-card";
```

---

## 任务四：重构 DocumentReferencesCard

**文件**：`frontend/src/components/chat/sources-card.tsx`

### 4.1 移除 onOpenDocument

`DocumentReferencesCard` 不再需要导航回调，精简 Props 类型：

```typescript
type DocumentReferencesCardProps = {
  sources: NormalizedSource[];
};
```

### 4.2 新增 Popover 状态

在组件内部增加 `expandedIndex` 状态，记录当前展开的条目序号（`null` 表示全部折叠）：

```typescript
const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
```

点击逻辑：

- 点击当前已展开的条目 → 收起（设为 `null`）
- 点击其他条目 → 切换到该条目序号
- 点击外部区域 → 收起（见 4.3）

### 4.3 点击外部收起

使用 `useRef` 持有外层容器引用，在 `useEffect` 中监听 `document` 的 `pointerdown` 事件，当点击目标不在容器内时将 `expandedIndex` 重置为 `null`。依赖项为 `expandedIndex`，仅在有展开条目时注册监听，无展开时不注册。

```typescript
const containerRef = useRef<HTMLDivElement>(null);

useEffect(() => {
  if (expandedIndex === null) return;
  const handlePointerDown = (e: PointerEvent) => {
    if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
      setExpandedIndex(null);
    }
  };
  document.addEventListener("pointerdown", handlePointerDown);
  return () => document.removeEventListener("pointerdown", handlePointerDown);
}, [expandedIndex]);
```

### 4.4 条目按钮

原有 `onClick` 中的跳转逻辑替换为展开/收起 Popover 的逻辑：

```typescript
onClick={() => {
  setExpandedIndex((prev) => (prev === index ? null : index));
}}
```

`canOpen` 判断和 `onOpenDocument` 调用一并删除。`cursor` 改为始终 `"pointer"`（所有条目均可点击展开）。文档打开能力继续由 Sources 面板中的 `View` 提供。

### 4.5 Popover 渲染

Popover 在 sources 列表之后、"展开更多"按钮之前渲染。外层容器需要设置 `position: relative` 以使 Popover 的绝对定位生效。

Popover 的结构和样式要求：

- `position: absolute`，`left: 0`，`right: 0`（与卡片等宽）
- `z-index: 10` 以浮于消息气泡之上
- `max-height: 320px`，`overflow-y: auto`
- 边框和背景与卡片主体保持视觉连贯
- 内边距 `10px 12px`

文本展示规则：

- 展示完整的 `source.text`
- 若 `source.text.length > 1000`，在文本末尾另起一行展示灰色小字提示：`全文共 {n} 字`（`n` 为实际字符数）

Popover 仅在 `expandedIndex !== null` 时渲染对应条目的内容：

```tsx
{/* source detail popover */}
{expandedIndex !== null && sources[expandedIndex] && (
  <div
    style={{
      position: "absolute",
      left: 0,
      right: 0,
      zIndex: 10,
      maxHeight: 320,
      overflowY: "auto",
      padding: "10px 12px",
      background: "hsl(var(--card))",
      border: "1px solid hsl(var(--border))",
      borderRadius: "calc(var(--radius) - 2px)",
      boxShadow: "0 4px 12px hsl(var(--shadow) / 0.08)",
    }}
  >
    <p style={{ fontSize: 12, lineHeight: 1.7, margin: 0, whiteSpace: "pre-wrap" }}>
      {sources[expandedIndex].text}
    </p>
    {sources[expandedIndex].text.length > 1000 && (
      <p
        className="muted"
        style={{ fontSize: 11, marginTop: 6, marginBottom: 0 }}
      >
        全文共 {sources[expandedIndex].text.length} 字
      </p>
    )}
  </div>
)}
```

---

## 任务五：更新 message-item.tsx

**文件**：`frontend/src/components/chat/message-item.tsx`

移除对 `sourcesType` 的分支判断，始终渲染 `DocumentReferencesCard`，同时移除 `onOpenDocument` 传参：

```tsx
{message.sources && message.sources.length > 0 && (
  <div style={{ marginTop: 8 }}>
    <DocumentReferencesCard sources={message.sources} />
  </div>
)}
```

`MessageItemProps` 中的 `onOpenDocument` 字段保留（该 prop 由 `chat-panel.tsx` 传入，其他地方仍在使用），但不再向 `DocumentReferencesCard` 传递。

---

## 任务六：清理 i18n 字符串

**文件**：`frontend/src/lib/i18n/strings.ts`

删除 `uiStrings.sources.toolResults` 字段（原用于 `ToolResultsCard` 的标题 "工具调用结果"）。确认该字段没有其他引用后删除。

---

## 改动优先级与预期效果

| 任务 | 文件 | 改动量 | 优先级 | 预期效果 |
|------|------|--------|--------|----------|
| 任务一：后端动态 sources_type | `chat_service.py` | 小 | P0 | 来源类型语义与后续扩展兼容 |
| 任务二：前端类型精简 | 3 个 ts 文件 | 小 | P0 | 类型定义与后端行为对齐 |
| 任务三：删除 ToolResultsCard | `sources-card.tsx`、`message-item.tsx` | 小 | P0 | 消除冗余组件和分支 |
| 任务四：重构 DocumentReferencesCard | `sources-card.tsx` | 中 | P0 | 统一渲染，新增 Popover |
| 任务五：更新 message-item | `message-item.tsx` | 小 | P0 | 消除 sourcesType 分支 |
| 任务六：清理 i18n | `strings.ts` | 极小 | P1 | 清理无用字符串 |

---

## 测试与验收

1. 前端单元测试
- 运行 `frontend` 下的 `vitest`，确保 `message-item` 相关测试通过。
- 补充或验证 `DocumentReferencesCard` 交互：点击展开、再次点击收起、点击外部收起。

2. 后端单元测试
- 运行 `chat_service` 相关测试，验证 `sources_type` 在 `retrieval`、混合来源、空来源三种场景输出正确。

3. 端到端验证（服务已启动）
- Ask 与 Agent 分别发起一轮触发 `knowledge_base` 的问题，确认消息下方统一展示同一种引用卡片。
- 点击任意引用条目，确认出现完整文本 Popover，且不会跳转文档页面。
- 在左侧 Sources 面板点击 `View`，确认文档仍可正常打开（阅读入口未回退）。

---

## 不在本次实施范围内

- 引用来源点击跳转至文档内精确位置
- ES `chunk_id` 为空字符串的修复
- `source.score` 评分的前端可视化
