# Session 模块前端问题分析

## 概述

本文档分析"新建 Notebook 后直接进入 Markdown Viewer，点击 Explain/Conclude 出现'请先创建会话'提示"的前端完整链路，并给出修复方案。

与后端分析文档（`backend-analysis.md`）配合阅读，两者分别描述同一问题的前后端侧面。

---

## 问题复现路径

1. 打开空 Notebook（新建，未创建过任何 Session）
2. 在 Sources 面板关联文档，点击 **View** 进入 Markdown Viewer
3. 在文档中选中文字，点击浮出的 **解释 / 总结** 按钮
4. `ExplainCard` 弹出，显示："**请先创建会话**"（`uiStrings.explainCard.createSessionFirst`）
5. 用户必须：关闭 viewer → 回到 Chat 面板 → 手动点"新建会话" → 再次进入 viewer 操作

**期望行为**：步骤 3 触发时，若无会话则自动创建一个，直接执行 explain/conclude，无需用户感知。

---

## 数据流与代码链路

### 1. 用户点击 Explain/Conclude

**文件**：`frontend/src/components/notebooks/notebook-workspace.tsx`，第 58–69 行

```tsx
onExplain={({ documentId, selectedText }) =>
  sendByMode(t(uiStrings.workspace.explainPrompt), "explain", {
    document_id: documentId,
    selected_text: selectedText,
  })
}
onConclude={({ documentId, selectedText }) =>
  sendByMode(t(uiStrings.workspace.concludePrompt), "conclude", {
    document_id: documentId,
    selected_text: selectedText,
  })
}
```

`sendByMode` 直接委托给 `chat.sendMessage(text, mode, context)`。

### 2. sendMessage 中的 Session 判断

**文件**：`frontend/src/lib/hooks/useChatSession.ts`，第 586–614 行

```typescript
const sendMessage = useCallback(
  async (message, mode, context, sourceDocumentIds) => {
    const isExplainOrConclude = mode === "explain" || mode === "conclude";
    const hasCurrentSession =
      !!currentSessionId && sessions.some((s) => s.session_id === currentSessionId);
    let resolvedSessionId = hasCurrentSession ? currentSessionId : null;

    // ① 有 sessions 但没选中：用第一个
    if (isExplainOrConclude && !resolvedSessionId && sessions.length > 0) {
      resolvedSessionId = sessions[0].session_id;
      setCurrentSessionId(resolvedSessionId);
    }

    // ② 无任何 session → 显示错误，直接返回
    if (isExplainOrConclude && !resolvedSessionId) {
      setExplainCard({
        visible: true,
        mode: explainMode,
        selectedText: context?.selected_text || "",
        content: t(uiStrings.explainCard.createSessionFirst),  // ← 问题触发点
        isStreaming: false,
      });
      setStreaming(false, null);
      return;  // ← 提前退出，不执行任何 API 调用
    }

    // ③ agent/ask 模式（非 explain/conclude）：自动创建 session
    const sessionId = isExplainOrConclude
      ? resolvedSessionId
      : await ensureSession(message.slice(0, 30));
    ...
  }
);
```

**问题核心**：`②` 处对 explain/conclude 的处理与 `③` 处对 agent/ask 的处理逻辑不对称：

- agent/ask：无 session → 调 `ensureSession()` 自动创建
- explain/conclude：无 session → **显示错误**，不自动创建

### 3. ExplainCard 显示错误内容

**文件**：`frontend/src/components/chat/explain-card.tsx`

`ExplainCard` 接收 `card.content = "请先创建会话"` 后，直接渲染为文本。没有引导操作，也没有"新建会话"按钮，用户只能关闭面板手动处理。

### 4. ensureSession 已有完整自动创建能力

**文件**：`frontend/src/lib/hooks/useChatSession.ts`，第 572–583 行

```typescript
const ensureSession = useCallback(
  async (titleHint?: string) => {
    if (currentSessionId) return currentSessionId;
    if (sessions.length > 0) {
      const recent = sessions[0].session_id;
      setCurrentSessionId(recent);
      return recent;
    }
    // 完全无 session → 自动 POST /sessions 创建
    const created = await createSessionMutation.mutateAsync(titleHint);
    return created.session_id;
  },
  [createSessionMutation, currentSessionId, sessions, setCurrentSessionId]
);
```

`ensureSession` 完全具备"无 session 时自动创建"的能力，但只被 agent/ask 路径使用。

---

## 修复方案

### 方案一：让 explain/conclude 复用 ensureSession（推荐）

在 `sendMessage` 中，将 explain/conclude 路径的错误分支替换为 `ensureSession()` 调用：

```typescript
// 修改前（第 599–614 行）
if (isExplainOrConclude && !resolvedSessionId && sessions.length > 0) {
  resolvedSessionId = sessions[0].session_id;
  setCurrentSessionId(resolvedSessionId);
}
if (isExplainOrConclude && !resolvedSessionId) {
  setExplainCard({ ..., content: t(uiStrings.explainCard.createSessionFirst), ... });
  setStreaming(false, null);
  return;
}

// 修改后
if (isExplainOrConclude && !resolvedSessionId) {
  // 无论是否有 session 列表，统一走 ensureSession
  resolvedSessionId = await ensureSession();
}
```

此方案**最小改动**：移除错误提示，复用已有的 `ensureSession` 逻辑，行为完全对齐 agent/ask。

### 方案二：在 ExplainCard 中增加"新建会话"快捷操作（退而求其次）

若需保留显式提示，将"请先创建会话"改为带按钮的提示：

```tsx
// explain-card.tsx
{card.content === CREATE_SESSION_SENTINEL ? (
  <div>
    <p>{t(uiStrings.explainCard.createSessionFirst)}</p>
    <button onClick={() => onCreateSession()}>
      {t(uiStrings.chat.newSession)}
    </button>
  </div>
) : (
  <MarkdownViewer content={card.content} />
)}
```

此方案改动面更大，且仍然需要用户额外点击，不如方案一流畅。

---

## i18n 涉及字符串

| key | zh | en | 状态 |
|---|---|---|---|
| `explainCard.createSessionFirst` | 请先创建会话 | Please create a session first | **修复后可移除** |
| `chat.defaultSessionTitle` | 会话 {n} | Session {n} | 保留，用于自动创建时的标题 |
| `chat.newSession` | 新建会话 | New session | 保留 |

修复后 `createSessionFirst` 字符串不再在正常流程中触发，但建议保留定义（不删），以防极端情况下仍需展示。

---

## 自动创建 Session 的标题来源

`ensureSession` 调用 `createSessionMutation.mutateAsync(titleHint)`，其中 `titleHint` 是消息前 30 个字符。对于 explain/conclude 场景，消息内容是固定的系统提示（如 `uiStrings.workspace.explainPrompt`），并不适合作为标题。

因此实现上仍建议不传 `titleHint`：

```typescript
resolvedSessionId = await ensureSession();   // 不传 titleHint
```

但这里有一个需要修正文档结论的点：`generateDefaultSessionTitle` 只用于“手动新建会话时生成下一个标题”，并不负责渲染“已有 title=null 的会话”。

如果后端直接创建了 `title=null` 的默认 Session，而前端没有额外处理，旧实现会在 Session 下拉框和删除确认中回退显示 `session_id.slice(0, 8)`，而不是"会话 1 / Session 1"。

因此最终实现新增了 `frontend/src/lib/chat/session-labels.ts`：

- 按 `created_at` 正序为未命名会话计算稳定序号
- 使用 `uiStrings.chat.defaultSessionTitle` 渲染 "会话 {n}" / "Session {n}"
- 在 `SessionSelect` 和 `ChatPanel` 两处统一复用

这保证了：

- explain/conclude 自动创建的 session 不会显示为 UUID 片段
- 后端 notebook 默认 session 也能正确显示本地化标题
- 手动新建 session 仍然沿用 `generateDefaultSessionTitle` 生成下一个默认名称

## 补充问题：未命名 Session 的显示与创建是两套逻辑

这个问题在分析阶段很容易混淆：

| 逻辑 | 位置 | 作用 |
|---|---|---|
| `generateDefaultSessionTitle` | `useChatSession.ts` | 手动点“新建会话”时，生成提交给后端的标题 |
| `session-labels.ts` | 新增 helper | 对已有 `title=null` 的 session 做前端展示兜底 |

因此“自动创建默认 session”要想得到正确 UX，需要同时满足两件事：

1. explain/conclude 在无 session 时自动建会话
2. title 为空的 session 在 UI 中按本地化规则展示，而不是显示 UUID 前缀

---

## 与后端的配合边界

| 职责 | 后端 | 前端 |
|---|---|---|
| 创建默认 Session（Notebook 创建时） | `POST /notebooks` 自动调 `session_service.create()` | 无需感知，`sessionQuery` 加载时自然获取 |
| 无 Session 时的兜底（Explain/Conclude） | 无需修改 | `ensureSession()` 替换错误提示 |
| Session 标题 i18n | 存 `title=null` | 通过 `session-labels.ts` 用 `defaultSessionTitle` 渲染展示 |

**两个修复均独立**：即使后端已自动创建了默认 Session，前端 `ensureSession()` 的替换仍然有价值，因为它消除了"历史 Notebook 无 Session"或"会话全被删除"场景下的同类 UX 问题。

---

## 受影响的文件清单

### 前端

| 文件 | 改动描述 |
|---|---|
| `frontend/src/lib/hooks/useChatSession.ts` | `sendMessage`：explain/conclude 路径改为调 `ensureSession()` |
| `frontend/src/lib/chat/session-labels.ts` | 为 `title=null` 的 session 生成稳定的本地化展示标题 |
| `frontend/src/components/chat/session-select.tsx` | Session 下拉框改用展示标题 helper |
| `frontend/src/components/chat/chat-panel.tsx` | 删除确认弹窗改用展示标题 helper |
| `frontend/tests/lib/hooks/useChatSession.explain-session.test.tsx` | 验证 explain 会自动创建 session |
| `frontend/tests/lib/chat/session-labels.test.ts` | 验证未命名 session 的标题按创建顺序渲染 |

### 后端（见 backend-analysis.md）

| 文件 | 改动描述 |
|---|---|
| `newbee_notebook/application/services/notebook_service.py` | Notebook 创建后自动创建默认 session |
| `newbee_notebook/core/session/session_manager.py` | `_reload_memory`：side track 改取最新 12 条 |
| `newbee_notebook/domain/repositories/message_repository.py` | 增加 `descending` 参数 |
| `newbee_notebook/infrastructure/persistence/repositories/message_repo_impl.py` | 实现 `descending` 排序 |
