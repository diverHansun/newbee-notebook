# 问题分析 - RAG 可用性预判机制

## 当前数据流

```
源头：source-list.tsx 轮询 GET /api/v1/notebooks/{id}/documents（每 3 秒）
  |
  v
SourcesPanel.onDocumentsUpdate() 回调
  |
  v
notebook-workspace.tsx: setDocuments(docs)
  |
  v
buildRagHint(documents, ti) --> ragHint: string | null
  |
  v
askBlocked = Boolean(ragHint)
  |
  +---> ChatPanel props: askBlocked, ragHint
          |
          +---> chat-panel.tsx: 黄色警告 banner（ragHint 内容）
          |
          +---> ChatInput props: askBlocked
                  |
                  +---> 发送按钮禁用（mode === "ask" && askBlocked）
                  +---> 红色 badge "RAG 不可用"
```

## 前端受影响代码清单

### 1. notebook-workspace.tsx

**文件路径:** `frontend/src/components/notebooks/notebook-workspace.tsx`

`buildRagHint` 函数（第 23-44 行）：

```typescript
function buildRagHint(
  documents: NotebookDocumentItem[],
  ti: ReturnType<typeof useLang>["ti"]
): string | null {
  const blocking = documents.filter((item) =>
    ["uploaded", "pending", "processing", "converted"].includes(item.status)
  );
  if (blocking.length === 0) return null;
  // ... 计算各状态数量，返回 i18n 字符串
}
```

使用点（第 54-55 行）：

```typescript
const ragHint = useMemo(() => buildRagHint(documents, ti), [documents, ti]);
const askBlocked = Boolean(ragHint);
```

向 ChatPanel 传递 props（第 107-108 行）：

```typescript
askBlocked={askBlocked}
ragHint={ragHint || undefined}
```

### 2. chat-panel.tsx

**文件路径:** `frontend/src/components/chat/chat-panel.tsx`

Props 类型定义（第 21-22 行）：

```typescript
askBlocked: boolean;
ragHint?: string;
```

Props 解构（第 40-41 行）：

```typescript
askBlocked,
ragHint,
```

黄色警告 banner（第 168-184 行）：

```tsx
{askBlocked && ragHint && (
  <div style={{
    margin: "12px 16px 0",
    padding: "10px 14px",
    background: "hsl(var(--bee-yellow-light))",
    border: "1px solid hsl(var(--bee-yellow) / 0.4)",
    borderLeft: "3px solid hsl(var(--bee-yellow))",
    borderRadius: "calc(var(--radius) - 2px)",
    fontSize: 13,
    color: "#92400E",
    lineHeight: 1.5,
  }}>
    {ragHint}
  </div>
)}
```

向 ChatInput 传递 props（第 211 行）：

```typescript
askBlocked={askBlocked}
```

### 3. chat-input.tsx

**文件路径:** `frontend/src/components/chat/chat-input.tsx`

Props 类型定义（第 16 行）：

```typescript
askBlocked: boolean;
```

Props 解构（第 55 行）：

```typescript
askBlocked,
```

发送拦截逻辑（第 71 行）：

```typescript
if (mode === "ask" && askBlocked) return;
```

发送按钮禁用（第 75 行）：

```typescript
const sendDisabled = !input.trim() || (mode === "ask" && askBlocked);
```

红色 badge（第 182-186 行）：

```tsx
{mode === "ask" && askBlocked && (
  <span className="badge badge-failed" style={{ fontSize: 10 }}>
    {t(uiStrings.chat.ragUnavailable)}
  </span>
)}
```

### 4. strings.ts

**文件路径:** `frontend/src/lib/i18n/strings.ts`

```typescript
// 第 66 行
ragUnavailable: { zh: "RAG 不可用", en: "RAG unavailable" },

// 第 479-482 行
ragHint: {
  zh: "文档处理中，RAG 暂不可用：等待 {queued}，处理中 {processing}，已转换待索引 {converted}。可先使用 Agent 模式。",
  en: "Documents are still processing, so RAG is unavailable: ...",
},
```

### 5. chat-input.test.tsx

**文件路径:** `frontend/src/components/chat/chat-input.test.tsx`

三处测试用例传入 `askBlocked={false}` prop（第 26、55、88 行），移除 `askBlocked` prop 后需要同步更新。

## 后端受影响代码清单

### 1. chat_service.py - _validate_mode_guard

**文件路径:** `newbee_notebook/application/services/chat_service.py`

核心守卫方法（第 659-698 行）：

```python
async def _validate_mode_guard(self, mode_enum, allowed_doc_ids, context, ...):
    rag_modes = (ModeType.ASK, ModeType.CONCLUDE, ModeType.EXPLAIN)  # <-- Ask 不应在此
    if (
        mode_enum in rag_modes
        and not allowed_doc_ids
        and (blocking_document_ids or [])
    ):
        raise DocumentProcessingError(...)  # HTTP 409
```

### 2. chat_service.py - 非流式路径

非流式路径（第 201 行）对所有模式无条件调用 `_validate_mode_guard`：

```python
await self._validate_mode_guard(
    mode_enum=mode_enum,
    allowed_doc_ids=allowed_doc_ids,
    ...
)
```

而流式路径（第 378 行）已经有跳过逻辑：

```python
if mode_enum not in {ModeType.CHAT, ModeType.AGENT}:
    await self._validate_mode_guard(...)
```

非流式路径需要与流式路径对齐，将 Ask 也排除在守卫调用之外。

### 3. chat_service.py - validate_mode_for_chat

公开方法（第 634-657 行），用于前端预校验模式可用性：

```python
async def validate_mode_for_chat(self, session_id, mode, context=None):
    """Validate requirements for conclude/explain before streaming responses."""
    ...
    await self._validate_mode_guard(...)
```

方法注释已说明其目的是"conclude/explain before streaming"，但当前实现对所有模式都调用守卫。需要增加 Ask 的跳过条件。

### 4. chat_service.py - blocking_warning 的 Ask 模式行为

流式路径和非流式路径都有 blocking_warning 逻辑（第 209-215 行和第 391-397 行）：

```python
if runtime_mode_enum is not ModeType.AGENT and blocking_warning:
    warnings.append(blocking_warning)
```

当 Ask 模式有已完成文档 + 有处理中文档时，会发送 `partial_documents` warning。这个 warning 无需移除，它是后端对"部分文档不在检索范围内"的合理提示，但鉴于前端不再展示 ragHint banner，需确认此 warning 的前端消费方式。

经核实，此 warning 通过 SSE 流发送给前端，前端在消息列表中以系统消息形式展示，与本次移除的 ragHint banner 是独立的 UI 元素。保持不动。

### 5. 后端测试文件

**文件路径:** `newbee_notebook/tests/unit/test_chat_service_guards.py`

相关测试用例：
- `test_validate_mode_guard_allows_ask_when_completed_docs_exist`（第 233 行）
- `test_validate_mode_guard_blocks_explain_when_target_document_is_not_completed`（第 248 行）
- `test_validate_mode_guard_keeps_conclude_selected_text_rule`（第 269 行）

Ask 相关测试需要更新以反映新行为：Ask 模式不再被守卫拦截。

## 前后端逻辑对比

| 场景 | 前端当前行为 | 后端当前行为 | 期望行为 |
|------|------------|------------|---------|
| 全部文档已完成 | 允许 Ask | 允许 Ask | 允许 Ask（不变） |
| 部分文档处理中，有已完成文档 | 禁用 Ask | 允许 Ask + warning | 允许 Ask（移除前端禁用） |
| 全部文档处理中，0 个已完成 | 禁用 Ask | 409 错误 | 允许 Ask，LLM 回复中提示无可检索文档 |
| 没有文档 | 允许 Ask | 允许 Ask | 允许 Ask（不变） |
| Explain/Conclude 目标文档未就绪 | N/A（阅读器不可打开） | 409 错误 | 409 错误（不变） |
