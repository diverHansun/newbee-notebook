# 设计规范 - 移除 RAG 可用性预判

## 前端变更

### 1. notebook-workspace.tsx

**删除 `buildRagHint` 函数**（第 23-44 行整体删除）。

**删除 `ragHint` 和 `askBlocked` 变量**（第 54-55 行）：

```typescript
// 删除以下两行
const ragHint = useMemo(() => buildRagHint(documents, ti), [documents, ti]);
const askBlocked = Boolean(ragHint);
```

**移除 ChatPanel 的 `askBlocked` 和 `ragHint` props**（第 107-108 行）：

```typescript
// 删除以下两行
askBlocked={askBlocked}
ragHint={ragHint || undefined}
```

**清理无用 import**：`buildRagHint` 删除后，如果 `useMemo` 不再被其他代码使用，从 import 中移除。同理检查 `uiStrings` 是否仍被其他代码引用。

注意：`documents` 状态和 `setDocuments` 仍然保留，因为 `onDocumentsUpdate={setDocuments}` 回调仍用于 SourcesPanel 内部的文档状态刷新。但需要确认 `documents` 状态是否在移除 `buildRagHint` 后还有其他消费者。如果没有，则 `documents` 状态、`setDocuments` 及 `onDocumentsUpdate` props 也可一并移除。实现时需根据实际代码确认。

### 2. chat-panel.tsx

**从 Props 类型中删除 `askBlocked` 和 `ragHint`**：

```typescript
// 删除
askBlocked: boolean;
ragHint?: string;
```

**从 Props 解构中删除对应字段**：

```typescript
// 删除
askBlocked,
ragHint,
```

**删除黄色警告 banner 的整个 JSX 块**（第 168-184 行）。

**移除向 ChatInput 传递的 `askBlocked` prop**（第 211 行）。

### 3. chat-input.tsx

**从 Props 类型中删除 `askBlocked`**：

```typescript
// 删除
askBlocked: boolean;
```

**从 Props 解构中删除 `askBlocked`**。

**简化发送逻辑**（第 71 行）：

```typescript
// 修改前
if (mode === "ask" && askBlocked) return;
// 修改后：删除这行，不再有模式级别的发送拦截
```

**简化 `sendDisabled` 计算**（第 75 行）：

```typescript
// 修改前
const sendDisabled = !input.trim() || (mode === "ask" && askBlocked);
// 修改后
const sendDisabled = !input.trim();
```

**删除红色 badge JSX**（第 182-186 行）：

```tsx
// 删除整个块
{mode === "ask" && askBlocked && (
  <span className="badge badge-failed" style={{ fontSize: 10 }}>
    {t(uiStrings.chat.ragUnavailable)}
  </span>
)}
```

**清理无用 import**：删除 badge 后，检查 `uiStrings.chat.ragUnavailable` 是否是 `uiStrings` 在该文件中的唯一引用。如果是，移除对应 import。

### 4. strings.ts

**删除 `ragUnavailable` 条目**（第 66 行）：

```typescript
// 删除
ragUnavailable: { zh: "RAG 不可用", en: "RAG unavailable" },
```

**删除 `ragHint` 条目**（第 479-482 行）：

```typescript
// 删除整个 ragHint 对象
ragHint: {
  zh: "文档处理中，RAG 暂不可用：等待 {queued}，处理中 {processing}，已转换待索引 {converted}。可先使用 Agent 模式。",
  en: "Documents are still processing, so RAG is unavailable: queued {queued}, processing {processing}, converted pending index {converted}. Agent mode is available in the meantime.",
},
```

### 5. chat-input.test.tsx

**移除所有测试用例中的 `askBlocked` prop**（第 26、55、88 行）。该 prop 删除后，测试渲染 ChatInput 组件时不再需要传入此 prop。

---

## 后端变更

### 1. _validate_mode_guard - 缩小 rag_modes 范围

**文件路径:** `newbee_notebook/application/services/chat_service.py`，第 669 行。

```python
# 修改前
rag_modes = (ModeType.ASK, ModeType.CONCLUDE, ModeType.EXPLAIN)

# 修改后
rag_modes = (ModeType.CONCLUDE, ModeType.EXPLAIN)
```

此修改使 Ask 模式不再被 `_validate_mode_guard` 的第一个条件拦截。Ask 请求在 0 个已完成文档时也能正常通过，knowledge_base 工具返回空结果，LLM 在回复中自然告知用户当前没有可检索的文档内容。

Explain 和 Conclude 的 409 守卫保持不变，因为这两个模式依赖具体文档内容，文档未就绪时阅读器无法打开。

### 2. 非流式路径 - 与流式路径对齐

**文件路径:** `newbee_notebook/application/services/chat_service.py`，第 201 行。

当前非流式路径对所有模式无条件调用守卫：

```python
# 修改前
await self._validate_mode_guard(
    mode_enum=mode_enum,
    allowed_doc_ids=allowed_doc_ids,
    ...
)
```

流式路径已有跳过逻辑（第 378 行）：

```python
if mode_enum not in {ModeType.CHAT, ModeType.AGENT}:
    await self._validate_mode_guard(...)
```

非流式路径需要增加同样的跳过条件。结合 rag_modes 缩小后，Ask 已不在守卫范围内，但为了两条路径的逻辑一致性，非流式路径也应该增加跳过判断：

```python
# 修改后
if mode_enum not in {ModeType.CHAT, ModeType.AGENT}:
    await self._validate_mode_guard(
        mode_enum=mode_enum,
        allowed_doc_ids=allowed_doc_ids,
        ...
    )
```

这样两条路径的守卫调用逻辑完全一致：CHAT 和 AGENT 跳过守卫，ASK 进入守卫但不被 rag_modes 拦截（因为已从元组中移除），CONCLUDE 和 EXPLAIN 正常接受守卫校验。

### 3. validate_mode_for_chat - 增加 Ask 跳过

**文件路径:** `newbee_notebook/application/services/chat_service.py`，第 634-657 行。

此方法用于前端预校验模式可用性。方法注释已写明"Validate requirements for conclude/explain"，但实现对所有模式都调用守卫。增加跳过条件：

```python
# 修改后
async def validate_mode_for_chat(self, session_id, mode, context=None):
    """Validate requirements for conclude/explain before streaming responses."""
    session = await self._session_repo.get(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")
    mode_enum = ModeType(mode)
    if mode_enum in {ModeType.CHAT, ModeType.AGENT, ModeType.ASK}:
        return  # 这三种模式不需要预校验
    (
        allowed_doc_ids,
        docs_by_status,
        blocking_doc_ids,
        _,
    ) = await self._get_notebook_scope(session.notebook_id)
    await self._validate_mode_guard(
        mode_enum=mode_enum,
        allowed_doc_ids=allowed_doc_ids,
        context=context,
        notebook_id=session.notebook_id,
        documents_by_status=docs_by_status,
        blocking_document_ids=blocking_doc_ids,
    )
```

### 4. blocking_warning 行为

非流式路径（第 214 行）和流式路径（第 396 行）的 blocking_warning：

```python
if runtime_mode_enum is not ModeType.AGENT and blocking_warning:
    warnings.append(blocking_warning)
```

此逻辑保持不变。当 Ask 模式有已完成文档 + 有处理中文档时，`_build_blocking_warning` 仍然生成 `partial_documents` warning 发送给前端。这个 warning 通过 SSE 流以系统消息形式展示，与本次删除的 ragHint banner 是独立的 UI 路径，不受影响。

---

## 不变的部分

| 模块 | 说明 |
|------|------|
| source-list.tsx 轮询逻辑 | 3 秒轮询保持不变，用于更新 Sources 面板文档状态 |
| source-card.tsx 状态展示 | 文档处理进度 badge 保持不变 |
| Explain/Conclude 的 409 守卫 | 保留，这两个模式依赖具体文档内容 |
| `_build_blocking_warning` | 保留，部分文档处理中的 warning 是合理的提示 |
| 文档状态类型定义 | `DocumentStatus`、`ProcessingStage` 不变 |
| isNonTerminalStatus 判断 | 保留，用于控制轮询频率 |
