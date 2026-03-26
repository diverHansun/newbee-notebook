# 进度指示器：实施指南

## 实施顺序

按依赖关系从底层到上层：

1. i18n 词条 (`strings.ts`)
2. SSE 事件类型 (`types.ts`)
3. Store 扩展 (`chat-store.ts`)
4. 事件处理 (`useChatSession.ts`)
5. 渲染组件 (`message-item.tsx`)
6. 样式 (`thinking-indicator.css`)

---

## 第 1 步：新增 i18n 词条

**文件**: `frontend/src/lib/i18n/strings.ts`

在 `uiStrings` 对象中新增 `tools` 分组：

```typescript
tools: {
  knowledgeBase: { zh: "检索知识库", en: "Searching knowledge base" },
  webSearch:     { zh: "搜索网络", en: "Searching the web" },
  webCrawl:      { zh: "抓取网页", en: "Fetching web page" },
  getTime:       { zh: "获取时间", en: "Getting time" },
},
```

插入位置：`thinking` 分组之后。

---

## 第 2 步：新增 SSE 事件类型

**文件**: `frontend/src/lib/api/types.ts`

在 `SseEvent` 联合类型中新增两个成员：

```typescript
export type SseEventToolCall = {
  type: "tool_call";
  tool_name: string;
  tool_call_id: string;
  tool_input: Record<string, unknown>;
};

export type SseEventToolResult = {
  type: "tool_result";
  tool_name: string;
  tool_call_id: string;
  success: boolean;
  content_preview: string;
  quality_meta: Record<string, unknown> | null;
};
```

更新 `SseEvent` 联合类型：

```typescript
export type SseEvent =
  | SseEventStart
  | SseEventContent
  | SseEventThinking
  | SseEventSources
  | SseEventConfirmation
  | SseEventDone
  | SseEventError
  | SseEventHeartbeat
  | SseEventToolCall      // 新增
  | SseEventToolResult;   // 新增
```

---

## 第 3 步：扩展 Zustand Store

**文件**: `frontend/src/stores/chat-store.ts`

### 3a. 新增 ToolStep 类型

在文件顶部（`PendingConfirmation` 类型之后）：

```typescript
export type ToolStep = {
  id: string;
  toolName: string;
  status: "running" | "done" | "error";
};
```

### 3b. ChatMessage 新增字段

```typescript
export type ChatMessage = {
  // ... 现有字段不变
  toolSteps?: ToolStep[];   // 新增
};
```

### 3c. ChatState 新增 action 签名

```typescript
type ChatState = {
  // ... 现有字段和 action 不变
  addToolStep: (id: string, step: ToolStep) => void;
  updateToolStep: (id: string, toolCallId: string, status: ToolStep["status"]) => void;
};
```

### 3d. action 实现

```typescript
addToolStep: (id, step) =>
  set((state) => ({
    messages: state.messages.map((msg) =>
      msg.id === id
        ? { ...msg, toolSteps: [...(msg.toolSteps || []), step] }
        : msg
    ),
  })),

updateToolStep: (id, toolCallId, status) =>
  set((state) => ({
    messages: state.messages.map((msg) =>
      msg.id === id
        ? {
            ...msg,
            toolSteps: (msg.toolSteps || []).map((s) =>
              s.id === toolCallId ? { ...s, status } : s
            ),
          }
        : msg
    ),
  })),
```

---

## 第 4 步：事件处理

**文件**: `frontend/src/lib/hooks/useChatSession.ts`

### 4a. 从 store 解构新 action

在 `useChatSession` hook 内部，从 `useChatStore` 解构新增的 action：

```typescript
const {
  // ... 现有解构
  addToolStep,
  updateToolStep,
} = useChatStore();
```

### 4b. 在 onEvent 回调中新增处理分支

在 `onEvent` 回调中，`"thinking"` 分支之后、`"sources"` 分支之前插入：

```typescript
if (event.type === "tool_call") {
  if (activeAssistantIdRef.current) {
    addToolStep(activeAssistantIdRef.current, {
      id: event.tool_call_id,
      toolName: event.tool_name,
      status: "running",
    });
  }
  return;
}
if (event.type === "tool_result") {
  if (activeAssistantIdRef.current) {
    updateToolStep(
      activeAssistantIdRef.current,
      event.tool_call_id,
      event.success ? "done" : "error",
    );
  }
  return;
}
```

注意事项：
- 这两个分支的位置不影响功能，但放在 `"thinking"` 之后符合事件时序逻辑
- `activeAssistantIdRef.current` 的守卫条件与现有分支保持一致

---

## 第 5 步：渲染组件

**文件**: `frontend/src/components/chat/message-item.tsx`

### 5a. 新增 toolDisplayLabel 函数

在 `thinkingStageLabel` 函数之后：

```typescript
function toolDisplayLabel(toolName: string, t: TranslateFn): string {
  const known: Record<string, LocalizedString> = {
    knowledge_base:   uiStrings.tools.knowledgeBase,
    tavily_search:    uiStrings.tools.webSearch,
    tavily_crawl:     uiStrings.tools.webCrawl,
    zhipu_web_search: uiStrings.tools.webSearch,
    zhipu_web_crawl:  uiStrings.tools.webCrawl,
    time:             uiStrings.tools.getTime,
  };
  if (known[toolName]) return t(known[toolName]);
  return toolName.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}
```

### 5b. 新增 ToolStepsIndicator 组件

在 `ThinkingIndicator` 组件之后：

```typescript
function ToolStepsIndicator({
  steps,
  thinkingStage,
  t,
}: {
  steps: ToolStep[];
  thinkingStage?: string | null;
  t: TranslateFn;
}) {
  const isSynthesizing = thinkingStage === "synthesizing";

  return (
    <div className="tool-steps-indicator" role="status" aria-live="polite">
      <div className="tool-steps-list">
        {steps.map((step) => (
          <div key={step.id} className={`tool-step tool-step--${step.status}`}>
            <span className="tool-step-icon" aria-hidden="true" />
            <span className="tool-step-label">
              {toolDisplayLabel(step.toolName, t)}
              {step.status === "running" ? "..." : ""}
            </span>
          </div>
        ))}
        {isSynthesizing ? (
          <div className="tool-step tool-step--running">
            <span className="tool-step-icon" aria-hidden="true" />
            <span className="tool-step-label">
              {t(uiStrings.thinking.generating)}
            </span>
          </div>
        ) : null}
      </div>
      <div className="tool-steps-progress" aria-hidden="true">
        <span className="tool-steps-progress-bar" />
      </div>
    </div>
  );
}
```

### 5c. 修改 MessageItem 渲染条件

将现有的 `showThinkingIndicator` 判断区域替换为：

```typescript
const hasToolSteps =
  !isUser &&
  message.status === "streaming" &&
  !message.content &&
  message.toolSteps &&
  message.toolSteps.length > 0;

const showThinkingIndicator =
  !isUser && message.status === "streaming" && !message.content && !hasToolSteps;
```

渲染部分：

```tsx
{showThinkingIndicator ? (
  <ThinkingIndicator stage={message.thinkingStage} t={t} />
) : hasToolSteps ? (
  <ToolStepsIndicator
    steps={message.toolSteps!}
    thinkingStage={message.thinkingStage}
    t={t}
  />
) : (
  <div className={`card${isUser ? "" : " message-bubble-assistant"}`} ...>
    {/* 现有消息内容渲染，不变 */}
  </div>
)}
```

### 5d. 消失动画

当 content delta 到达时，`appendMessageContent` 已经将 `thinkingStage` 设为 null 并填充 content，触发条件切换。

要实现渐隐效果，有两种方案：

**方案 A（简单版，推荐）**: 直接切换，不做渐隐。当前 ThinkingIndicator 也是直接消失的，保持行为一致。

**方案 B（渐隐版）**: 使用 CSS animation。在 content 到达前的最后一帧，给容器加 `tool-steps-indicator--exiting` class，利用 `animationend` 事件触发移除。这需要在 store 中增加一个 `toolStepsExiting` 布尔字段，增加了复杂度。

建议先实现方案 A，后续如果用户体验需要再追加方案 B。方案 B 的 CSS 已在 [css-style-spec.md](./css-style-spec.md) 中预定义。

---

## 第 6 步：样式

详见 [css-style-spec.md](./css-style-spec.md)。

---

## 测试要点

### 场景覆盖

1. **无工具调用**（纯 LLM 推理）: 应显示原有 ThinkingIndicator，行为不变
2. **单工具调用**（如 knowledge_base）: 显示一个步骤，running -> done -> synthesizing -> content
3. **多工具调用**（如 knowledge_base + tavily_search）: 显示多个步骤，按到达顺序排列
4. **工具调用失败**（success=false）: 步骤显示 error 状态
5. **用户取消**（abort）: 步骤列表应随消息状态变为 cancelled 而消失
6. **工具确认流程**（confirmation_request）: tool_call 在确认前发出，确认后继续正常流程
7. **Explain/Conclude 模式**: 这些模式在 ExplainCard 中渲染，不受影响

### 回归检查

- 现有 ThinkingIndicator 在无工具调用场景下行为不变
- 消息内容渲染不受影响
- Sources 卡片显示不受影响
- ConfirmationCard 显示不受影响
- SSE 流超时回退机制不受影响
