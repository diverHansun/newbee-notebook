# Tool Steps Progress Indicator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display granular, tool-level progress during AI message generation, replacing the single "AI is thinking..." indicator when tool calls are active.

**Architecture:** Frontend-only changes across 6 files. The backend already emits `tool_call` and `tool_result` SSE events; the frontend currently ignores them. We add SSE type definitions, extend the Zustand chat store with a `toolSteps` array, handle the two new event types in the session hook, and render them in a new `ToolStepsIndicator` component.

**Tech Stack:** React, Zustand, CSS (no new dependencies)

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/src/lib/i18n/strings.ts` | Modify | Add `tools.*` i18n entries |
| `frontend/src/lib/api/types.ts` | Modify | Add `SseEventToolCall`, `SseEventToolResult` types |
| `frontend/src/stores/chat-store.ts` | Modify | Add `ToolStep` type, `toolSteps` field, 2 new actions |
| `frontend/src/lib/hooks/useChatSession.ts` | Modify | Handle `tool_call` / `tool_result` SSE events |
| `frontend/src/components/chat/message-item.tsx` | Modify | Add `ToolStepsIndicator` component, update render logic |
| `frontend/src/styles/thinking-indicator.css` | Modify | Add `.tool-steps-*` CSS classes |

---

### Task 1: Add i18n Tool Labels

**Files:**
- Modify: `frontend/src/lib/i18n/strings.ts:28` (after `thinking` block)

- [ ] **Step 1: Add `tools` i18n entries**

Insert after the `thinking` block (line 28), before `chat`:

```typescript
  tools: {
    knowledgeBase: { zh: "检索知识库", en: "Searching knowledge base" },
    webSearch: { zh: "搜索网络", en: "Searching the web" },
    webCrawl: { zh: "抓取网页", en: "Fetching web page" },
    getTime: { zh: "获取时间", en: "Getting time" },
  },
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx next build --no-lint 2>&1 | tail -5`
Expected: Build completes (or dev server shows no errors if running)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/i18n/strings.ts
git commit -m "feat(i18n): add tool display label entries for progress indicator"
```

---

### Task 2: Add SSE Event Types

**Files:**
- Modify: `frontend/src/lib/api/types.ts:303-313`

- [ ] **Step 1: Add `SseEventToolCall` and `SseEventToolResult` types**

Insert after `SseEventConfirmation` (after line 303), before the `SseEvent` union:

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

- [ ] **Step 2: Add both to the `SseEvent` union**

Replace the existing `SseEvent` union (lines 305-313):

```typescript
export type SseEvent =
  | SseEventStart
  | SseEventContent
  | SseEventThinking
  | SseEventSources
  | SseEventDone
  | SseEventError
  | SseEventHeartbeat
  | SseEventConfirmation
  | SseEventToolCall
  | SseEventToolResult;
```

- [ ] **Step 3: Verify no type errors**

Run: `cd frontend && npx tsc --noEmit 2>&1 | tail -5`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api/types.ts
git commit -m "feat(types): add SseEventToolCall and SseEventToolResult SSE event types"
```

---

### Task 3: Extend Zustand Store

**Files:**
- Modify: `frontend/src/stores/chat-store.ts`

- [ ] **Step 1: Add `ToolStep` type after `PendingConfirmation`**

Insert after line 17 (closing `};` of `PendingConfirmation`):

```typescript

export type ToolStep = {
  id: string;
  toolName: string;
  status: "running" | "done" | "error";
};
```

- [ ] **Step 2: Add `toolSteps` field to `ChatMessage`**

Add after the `pendingConfirmation` field (line 30):

```typescript
  toolSteps?: ToolStep[];
```

- [ ] **Step 3: Add action signatures to `ChatState`**

Add after `appendMessageContent` signature (line 54):

```typescript
  addToolStep: (id: string, step: ToolStep) => void;
  updateToolStep: (id: string, toolCallId: string, status: ToolStep["status"]) => void;
```

- [ ] **Step 4: Implement `addToolStep` action**

Add after the `appendMessageContent` implementation (after line 93):

```typescript
  addToolStep: (id, step) =>
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id
          ? { ...msg, toolSteps: [...(msg.toolSteps || []), step] }
          : msg
      ),
    })),
```

- [ ] **Step 5: Implement `updateToolStep` action**

Add immediately after `addToolStep`:

```typescript
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

- [ ] **Step 6: Verify no type errors**

Run: `cd frontend && npx tsc --noEmit 2>&1 | tail -5`
Expected: No errors

- [ ] **Step 7: Commit**

```bash
git add frontend/src/stores/chat-store.ts
git commit -m "feat(store): add ToolStep type and addToolStep/updateToolStep actions"
```

---

### Task 4: Handle SSE Events in useChatSession

**Files:**
- Modify: `frontend/src/lib/hooks/useChatSession.ts`

- [ ] **Step 1: Destructure new actions from store**

In the destructuring block (lines 134-151), add `addToolStep` and `updateToolStep`:

Change:
```typescript
    appendExplainContent,
  } = useChatStore();
```
To:
```typescript
    appendExplainContent,
    addToolStep,
    updateToolStep,
  } = useChatStore();
```

- [ ] **Step 2: Add `tool_call` and `tool_result` event handlers**

In the `onEvent` callback, after the `"thinking"` block (after the block ending around line 531) and before the `"sources"` block, add:

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

- [ ] **Step 3: Verify no type errors**

Run: `cd frontend && npx tsc --noEmit 2>&1 | tail -5`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/hooks/useChatSession.ts
git commit -m "feat(chat-session): handle tool_call and tool_result SSE events"
```

---

### Task 5: Add ToolStepsIndicator Component and Update Rendering

**Files:**
- Modify: `frontend/src/components/chat/message-item.tsx`

- [ ] **Step 1: Add import for `ToolStep`**

Update the import from `chat-store` (line 8):

```typescript
import { ChatMessage, ToolStep } from "@/stores/chat-store";
```

- [ ] **Step 2: Add `toolDisplayLabel` function**

Insert after `thinkingStageLabel` function (after line 45):

```typescript

function toolDisplayLabel(toolName: string, t: TranslateFn): string {
  const known: Record<string, LocalizedString> = {
    knowledge_base: uiStrings.tools.knowledgeBase,
    tavily_search: uiStrings.tools.webSearch,
    tavily_crawl: uiStrings.tools.webCrawl,
    zhipu_web_search: uiStrings.tools.webSearch,
    zhipu_web_crawl: uiStrings.tools.webCrawl,
    time: uiStrings.tools.getTime,
  };
  if (known[toolName]) return t(known[toolName]);
  return toolName.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}
```

- [ ] **Step 3: Add `ToolStepsIndicator` component**

Insert after `ThinkingIndicator` component (after line 73):

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

- [ ] **Step 4: Update rendering conditions in `MessageItem`**

Replace the existing `showThinkingIndicator` variable (line 82-83):

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

- [ ] **Step 5: Update JSX render block**

Replace the message bubble section (lines 127-146):

```tsx
        {/* Message bubble */}
        {showThinkingIndicator ? (
          <ThinkingIndicator stage={message.thinkingStage} t={t} />
        ) : hasToolSteps ? (
          <ToolStepsIndicator
            steps={message.toolSteps!}
            thinkingStage={message.thinkingStage}
            t={t}
          />
        ) : (
          <div
            className={`card${isUser ? "" : " message-bubble-assistant"}`}
            style={{
              padding: isUser ? "12px 16px" : "12px 16px 12px 14px",
              background: isUser ? "hsl(var(--user-bubble-bg))" : "hsl(var(--card))",
              color: isUser ? "hsl(var(--user-bubble-fg))" : "hsl(var(--card-foreground))",
            }}
          >
            {isUser ? (
              <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                {message.content}
              </p>
            ) : (
              <MarkdownViewer content={message.content} />
            )}
          </div>
        )}
```

- [ ] **Step 6: Update status badge visibility**

The status badge condition (line 119) must also account for `hasToolSteps`:

```typescript
          {message.status && message.status !== "done" && !showThinkingIndicator && !hasToolSteps && (
```

- [ ] **Step 7: Verify no type errors**

Run: `cd frontend && npx tsc --noEmit 2>&1 | tail -5`
Expected: No errors

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/chat/message-item.tsx
git commit -m "feat(message-item): add ToolStepsIndicator component for tool call progress"
```

---

### Task 6: Add CSS Styles

**Files:**
- Modify: `frontend/src/styles/thinking-indicator.css`

- [ ] **Step 1: Append tool-steps CSS to thinking-indicator.css**

Append at the end of the file (after line 77):

```css
/* ================================================================
   22b. Tool Steps Indicator
   ================================================================ */

.tool-steps-indicator {
  max-width: 280px;
  border: 1px solid hsl(var(--border));
  border-radius: 8px;
  background: hsl(var(--muted) / 0.5);
  padding: 10px 14px;
}

.tool-steps-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tool-step {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 20px;
}

.tool-step-label {
  font-size: 12px;
  line-height: 1.4;
  color: hsl(var(--muted-foreground));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tool-step-icon {
  position: relative;
  width: 14px;
  height: 14px;
  flex: 0 0 14px;
  border-radius: 50%;
}

/* running: spinning ring */
.tool-step--running .tool-step-icon {
  background: conic-gradient(
    hsl(var(--bee-yellow)),
    hsl(var(--bee-amber)),
    hsl(var(--bee-yellow))
  );
  animation: thinking-spin 1s linear infinite;
}

.tool-step--running .tool-step-icon::after {
  content: "";
  position: absolute;
  inset: 2px;
  border-radius: 50%;
  background: hsl(var(--muted) / 0.5);
}

/* done: static checkmark */
.tool-step--done .tool-step-icon {
  background: hsl(var(--bee-amber) / 0.2);
}

.tool-step--done .tool-step-icon::after {
  content: "";
  position: absolute;
  top: 3px;
  left: 3px;
  width: 5px;
  height: 8px;
  border: solid hsl(var(--bee-amber));
  border-width: 0 1.5px 1.5px 0;
  transform: rotate(40deg);
}

.tool-step--done .tool-step-label {
  color: hsl(var(--muted-foreground) / 0.6);
}

/* error: red cross */
.tool-step--error .tool-step-icon {
  background: hsl(0 70% 50% / 0.2);
}

.tool-step--error .tool-step-icon::before,
.tool-step--error .tool-step-icon::after {
  content: "";
  position: absolute;
  top: 50%;
  left: 50%;
  width: 8px;
  height: 1.5px;
  background: hsl(0 70% 50%);
  border-radius: 1px;
}

.tool-step--error .tool-step-icon::before {
  transform: translate(-50%, -50%) rotate(45deg);
}

.tool-step--error .tool-step-icon::after {
  transform: translate(-50%, -50%) rotate(-45deg);
}

.tool-step--error .tool-step-label {
  color: hsl(0 70% 50% / 0.8);
}

/* bottom shimmer bar */
.tool-steps-progress {
  position: relative;
  margin-top: 8px;
  height: 2px;
  width: 100%;
  border-radius: 999px;
  background: hsl(var(--border));
  overflow: hidden;
}

.tool-steps-progress-bar {
  position: absolute;
  inset: 0 auto 0 0;
  width: 40%;
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    transparent 0%,
    hsl(var(--bee-yellow)) 40%,
    hsl(var(--bee-amber)) 60%,
    transparent 100%
  );
  animation: thinking-shimmer 1.2s linear infinite;
}

/* exit animation (reserved for future use) */
.tool-steps-indicator--exiting {
  animation: thinking-fade-out 0.4s ease-out forwards;
  pointer-events: none;
}
```

- [ ] **Step 2: Verify styles load**

Check the running dev server at `http://localhost:3000` - no CSS errors in console.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/styles/thinking-indicator.css
git commit -m "feat(css): add tool-steps indicator styles"
```

---

### Task 7: End-to-End Functional Test with Playwright

**Files:** None (test only)

- [ ] **Step 1: Test Agent mode (triggers tool calls)**

Open `http://localhost:3000/notebooks/db6080ce-bdd7-4362-b496-0d4523848ab4` in Playwright. Type a question in Agent mode (e.g. "这个笔记本有哪些文档?") and send. Observe:
- Tool steps indicator appears with specific tool names (e.g. "检索知识库...")
- Steps transition from running (spinning ring) to done (checkmark)
- After all tools complete, "正在生成回答..." appears
- Content replaces the indicator when streaming begins
- Take a screenshot to verify visual state

- [ ] **Step 2: Test Ask mode (always calls knowledge_base)**

Switch to Ask mode. Send a question. Observe:
- Tool steps indicator shows "检索知识库..." with running state
- Transitions to done, then synthesizing, then content
- Take a screenshot

- [ ] **Step 3: Test no-tool scenario (regression)**

If applicable, test a scenario where no tools are called (e.g. simple greeting in Agent mode). Verify:
- The original ThinkingIndicator ("AI 正在思考...") still appears
- No ToolStepsIndicator is shown

- [ ] **Step 4: Commit all work**

```bash
git add -A
git commit -m "feat(progress-bar): implement tool-level progress indicator for AI message generation"
```
