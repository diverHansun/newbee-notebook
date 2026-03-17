# Skill 前端交互

## 1. 设计目标

为 Chat 面板增加 Skill 交互能力：slash 命令提示、确认事件处理、确认回传。前端不解析 slash 命令语义（由后端 SkillRegistry 处理），仅提供输入辅助和确认 UI。

## 2. Slash 命令提示

### 2.1 触发条件

当用户在 ChatInput 的 textarea 中输入内容以 `/` 开头时，显示命令提示浮动面板。

检测逻辑：

```typescript
const showSlashHint = input.startsWith("/") && !input.includes(" ");
```

即仅在输入以 `/` 开头且尚未输入空格（还在输入命令名称阶段）时显示。输入空格后（进入消息正文阶段）自动隐藏。

### 2.2 命令列表

v1 硬编码，后续可改为从 API 获取：

```typescript
type SlashCommand = {
  command: string;
  label: LocalizedString;
  available: boolean;
};

const SLASH_COMMANDS: SlashCommand[] = [
  {
    command: "/note",
    label: { zh: "笔记和书签管理", en: "Notes & Marks management" },
    available: true,
  },
  {
    command: "/mindmap",
    label: { zh: "思维导图", en: "Mind Map" },
    available: false,
  },
];
```

### 2.3 浮动面板

在 textarea 上方弹出，复用 `.source-selector-panel` 的样式模式（绝对定位、border、card 背景、click-outside 关闭）。

```
+------------------------------------+
| /note   笔记和书签管理              |
| /mindmap 思维导图 (Coming Soon)     |
+------------------------------------+
| /note help me create...            |
| [Agent  Ask]  ...            [->]  |
+------------------------------------+
```

面板内容：
- 过滤：根据已输入的文本过滤命令列表（如输入 `/n` 只显示 `/note`）
- 不可用命令灰显，不可选择
- 键盘导航：上下键选择，Enter/Tab 补全，Escape 关闭
- 点击可用命令：补全到 textarea（如 `/note `，末尾带空格），面板关闭

### 2.4 组件设计

新建 `SlashCommandHint` 组件，作为 ChatInput 内部的条件渲染子组件：

```typescript
type SlashCommandHintProps = {
  input: string;
  onSelect: (command: string) => void;
  onDismiss: () => void;
};
```

渲染条件：`showSlashHint && SLASH_COMMANDS.length > 0`。

### 2.5 模式自动切换

当用户输入以已知 slash 命令开头的消息时（如 `/note ...`），前端不修改 mode。后端 ChatService 负责在检测到 skill 命令时自动切换到 agent mode。

但前端可以做一个小优化：如果当前 mode 是 `ask` 且输入以 `/` 开头，自动切换 mode 为 `agent`。此优化为可选项。

## 3. SSE 确认事件处理

### 3.1 新增 SSE 事件类型

在 `types.ts` 中新增：

```typescript
export type SseEventConfirmation = {
  type: "confirmation_request";
  request_id: string;
  tool_name: string;
  tool_args: Record<string, unknown>;
  description: string;
};

export type SseEvent =
  | SseEventStart
  | SseEventContent
  | SseEventThinking
  | SseEventSources
  | SseEventDone
  | SseEventError
  | SseEventHeartbeat
  | SseEventConfirmation;  // 新增
```

### 3.2 后端事件对应

后端 `ConfirmationRequestEvent` 经过 ChatService 和 SSE adapter 转换后，前端收到的 SSE 数据格式：

```json
{
  "type": "confirmation_request",
  "request_id": "uuid",
  "tool_name": "update_note",
  "tool_args": {"note_id": "xxx", "content": "..."},
  "description": "更新笔记[标题]的内容"
}
```

### 3.3 useChatSession 事件处理

在 `sendMessage` 的 `onEvent` 回调中新增分支：

```typescript
if (event.type === "confirmation_request") {
  if (activeAssistantIdRef.current) {
    updateMessage(activeAssistantIdRef.current, {
      pendingConfirmation: {
        requestId: event.request_id,
        toolName: event.tool_name,
        toolArgs: event.tool_args,
        description: event.description,
        status: "pending",
      },
    });
  }
  return;
}
```

SSE 连接在确认等待期间保持打开。后端 AgentLoop 通过 `asyncio.Event.wait()` 暂停，heartbeat 持续发送以保持连接。用户确认/拒绝后，后端继续发送后续事件（content、done 等），前端正常处理。

### 3.4 超时机制

前后端统一超时时间：**3 分钟（180 秒）**。

- 后端：AgentLoop 的 `asyncio.wait_for(confirmation_event.wait(), timeout=180)` 超时后自动取消工具调用，向 agent 反馈超时信息，流继续
- 前端：收到 `confirmation_request` 后启动 180 秒计时器。超时后将确认卡片状态设为 `"timeout"`，显示超时提示。后端的后续 SSE 事件（agent 的超时后回复）会自然到达并更新 UI

```typescript
const CONFIRMATION_TIMEOUT_MS = 180_000;

// 在收到 confirmation_request 时
const timer = window.setTimeout(() => {
  updateMessage(assistantId, {
    pendingConfirmation: { ...confirmation, status: "timeout" },
  });
}, CONFIRMATION_TIMEOUT_MS);

// 在用户操作或 SSE 流结束时清除
window.clearTimeout(timer);
```

## 4. 内联确认卡片

### 4.1 设计理念

确认请求作为 agent 对话流的一部分，渲染为消息内联卡片，而非模态弹窗。这与现有的 `DocumentReferencesCard` 和 `ToolResultsCard` 处于同一层级。

理由：
- 保持对话上下文可见（用户能看到 agent 之前说了什么）
- 与现有消息卡片模式一致
- 不阻断页面其他操作

### 4.2 ChatMessage 类型扩展

```typescript
type PendingConfirmation = {
  requestId: string;
  toolName: string;
  toolArgs: Record<string, unknown>;
  description: string;
  status: "pending" | "confirmed" | "rejected" | "timeout";
};

type ChatMessage = {
  id: string;
  messageId?: number;
  role: MessageRole;
  mode: MessageMode;
  content: string;
  status: "streaming" | "done" | "error" | "cancelled";
  createdAt: string;
  thinkingStage?: string | null;
  sources?: Source[];
  sourcesType?: string;
  pendingConfirmation?: PendingConfirmation;  // 新增
};
```

### 4.3 ConfirmationCard 组件

新建 `ConfirmationCard` 组件：

```typescript
type ConfirmationCardProps = {
  confirmation: PendingConfirmation;
  onConfirm: () => void;
  onReject: () => void;
};
```

渲染逻辑：

**status = "pending"**：

```
+-------------------------------------+
|  [!] 确认操作                        |
|                                     |
|  update_note                        |
|  更新笔记"大模型学习笔记"的内容      |
|                                     |
|           [确认]    [拒绝]          |
+-------------------------------------+
```

**status = "confirmed"**：

```
+-------------------------------------+
|  [v] 已确认  update_note            |
+-------------------------------------+
```

**status = "rejected"**：

```
+-------------------------------------+
|  [x] 已拒绝  update_note            |
+-------------------------------------+
```

**status = "timeout"**：

```
+-------------------------------------+
|  [!] 已超时  update_note             |
+-------------------------------------+
```

### 4.4 样式

复用 `.card` 基础类，增加左侧边框标识：

```css
.confirmation-card {
  border-left: 3px solid var(--bee-amber);
  padding: 12px 16px;
}

.confirmation-card--confirmed {
  border-left-color: var(--primary);
  opacity: 0.7;
}

.confirmation-card--rejected {
  border-left-color: var(--destructive);
  opacity: 0.7;
}

.confirmation-card--timeout {
  border-left-color: var(--muted-foreground);
  opacity: 0.7;
}
```

已处理状态（confirmed/rejected/timeout）收起为单行摘要，减少视觉占用。

### 4.5 在 MessageItem 中渲染

```tsx
// message-item.tsx 中 assistant 消息内容区域
{message.content && <MarkdownViewer content={message.content} />}
{message.pendingConfirmation && (
  <ConfirmationCard
    confirmation={message.pendingConfirmation}
    onConfirm={() => handleConfirmAction(true)}
    onReject={() => handleConfirmAction(false)}
  />
)}
{message.sources && <DocumentReferencesCard ... />}
```

确认卡片渲染在消息内容之后、来源引用之前。

## 5. 确认回传 API

### 5.1 API 函数

```typescript
// lib/api/chat.ts 新增
export function confirmAction(params: {
  session_id: string;
  request_id: string;
  approved: boolean;
}) {
  return apiFetch<void>("/chat/confirm", {
    method: "POST",
    body: params,
  });
}
```

### 5.2 调用时机

在 `useChatSession` 中新增 `handleConfirmAction`：

```typescript
const handleConfirmAction = useCallback(
  async (messageId: string, approved: boolean) => {
    const message = messages.find((m) => m.id === messageId);
    if (!message?.pendingConfirmation || !currentSessionId) return;
    if (message.pendingConfirmation.status !== "pending") return;

    const { requestId } = message.pendingConfirmation;

    updateMessage(messageId, {
      pendingConfirmation: {
        ...message.pendingConfirmation,
        status: approved ? "confirmed" : "rejected",
      },
    });

    await confirmAction({
      session_id: currentSessionId,
      request_id: requestId,
      approved,
    });
  },
  [messages, currentSessionId, updateMessage]
);
```

此函数通过 `useChatSession` 返回值暴露给 `ChatPanel`，再传递给 `MessageItem`。

## 6. 变更范围汇总

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| types.ts | 类型扩展 | 新增 SseEventConfirmation |
| chat.ts (API) | 新增函数 | confirmAction() |
| chat-store.ts | 类型扩展 | ChatMessage 新增 pendingConfirmation 字段 |
| useChatSession.ts | 逻辑扩展 | onEvent 新增 confirmation_request 分支 + handleConfirmAction |
| chat-input.tsx | 新增子组件 | SlashCommandHint 条件渲染 |
| message-item.tsx | 新增子组件 | ConfirmationCard 条件渲染 |
| SlashCommandHint.tsx | 新建 | slash 命令提示浮动面板 |
| ConfirmationCard.tsx | 新建 | 内联确认卡片 |
| skill-frontend.css | 新建 | 确认卡片和命令提示样式 |
