# AI Message 中间态消息 — 前端开发计划

## 概述

本文档描述前端如何接收和渲染 Agent Loop 的中间态消息（Intermediate Content）：当 LLM 在 reasoning 阶段返回 tool_calls 的同时附带 content 文本时，前端需要在消息气泡中实时显示该文本，并与 ToolStepsIndicator 共存。

与后端分析文档（`../backend/intermediate-content-plan.md`）配合阅读，两者分别描述同一功能的前后端实现。

---

## 一、现状分析

### 1.1 当前行为

**文件**：`frontend/src/components/chat/message-item.tsx`，第 149–225 行

消息气泡区域的渲染逻辑是三选一：

```typescript
const hasToolSteps = !isUser && message.status === "streaming"
  && !message.content && message.toolSteps && message.toolSteps.length > 0;
const showThinkingIndicator = !isUser && message.status === "streaming"
  && !message.content && !hasToolSteps;

// 渲染：
// showThinkingIndicator → ThinkingIndicator（spinner + 阶段文字）
// hasToolSteps          → ToolStepsIndicator（工具步骤列表）
// 其他                  → 消息气泡（MarkdownViewer 渲染终结态 content）
```

**问题**：在 reasoning → retrieving 阶段（LLM 调用工具），用户只能看到 ThinkingIndicator 或 ToolStepsIndicator，无法看到 LLM 的中间态思考文本。

### 1.2 当前 SSE 事件处理

**文件**：`frontend/src/lib/hooks/useChatSession.ts`，第 586–850 行

`sendMessage()` 中通过 `onEvent` 回调处理 SSE 事件：

```typescript
if (event.type === "content")   → appendMessageContentInSession(...)
if (event.type === "thinking")  → updateThinkingStageInSession(...)
if (event.type === "tool_call") → addToolStepInSession(...)
if (event.type === "tool_result") → updateToolStepInSession(...)
if (event.type === "sources")   → updateMessageInSession(...)
if (event.type === "done")      → 完成处理
```

没有 `intermediate_content` 的处理分支。

### 1.3 当前消息状态模型

**文件**：`frontend/src/stores/chat-store.ts`

```typescript
export type ChatMessage = {
  id: string;
  role: MessageRole;
  mode: MessageMode;
  content: string;              // 终结态内容
  thinkingStage?: string | null;
  toolSteps?: ToolStep[];
  status?: "streaming" | "done" | "cancelled" | "error";
  // ... 其他字段
};
```

没有中间态内容字段。

### 1.4 当前数据流

```
SSE "phase"       → 更新 thinkingStage → ThinkingIndicator 切换阶段文字
SSE "tool_call"   → 添加 toolStep     → ToolStepsIndicator 显示工具步骤
SSE "tool_result"  → 更新 toolStep 状态
SSE "content"     → 写入 message.content → 消息气泡显示终结态文本
SSE "done"        → 设置 status="done"
```

用户在 reasoning 阶段只能看到"正在思考..."或工具步骤列表，无法看到 LLM 的中间态文本。

---

## 二、优化目标

1. 接收后端新增的 `intermediate_content` SSE 事件，实时显示中间态文本
2. 中间态文本在消息气泡中显示，与 ToolStepsIndicator 共存
3. 新一轮 reasoning 开始时，旧中间态文本渐隐消失，替换为新中间态文本
4. 最终态 content 到达时，中间态文本渐隐消失，替换为终结态内容
5. LLM 未返回中间态文本时，行为与当前完全一致（ThinkingIndicator / ToolStepsIndicator）

---

## 三、数据流修改

### 3.1 新增 SSE 事件

后端新增 `intermediate_content` 事件类型，格式：

```
data: {"type": "intermediate_content", "delta": "让我来"}
data: {"type": "intermediate_content", "delta": "查看一下"}
data: {"type": "intermediate_content", "delta": "知识库"}
```

### 3.2 修改后的数据流

```
SSE "phase"(reasoning)        → 清空 intermediateContent（如果是新一轮）
SSE "intermediate_content"    → 追加到 intermediateContent → 中间态气泡显示
SSE "tool_call"               → 添加 toolStep → ToolStepsIndicator 显示
SSE "tool_result"             → 更新 toolStep 状态
SSE "phase"(reasoning)        → 下一轮开始 → 渐隐清空 intermediateContent
SSE "intermediate_content"    → 新一轮中间态文本追加
SSE "phase"(synthesizing)     → 准备接收终结态
SSE "content"                 → 渐隐清空 intermediateContent → 写入 content → 终结态气泡
SSE "done"                    → 设置 status="done"
```

### 3.3 消息状态变化时序

```
状态 1：初始                    → ThinkingIndicator
状态 2：收到 intermediate delta → 中间态气泡 + ThinkingIndicator（无 toolSteps 时）
状态 3：收到 tool_call          → 中间态气泡 + ToolStepsIndicator
状态 4：新一轮 reasoning        → 旧中间态渐隐 → 新中间态气泡 + ToolStepsIndicator
状态 5：收到 content            → 中间态渐隐 → 终结态气泡（ToolStepsIndicator 消失）
```

---

## 四、实施方案

### 4.1 新增 SSE 事件类型

**文件**：`frontend/src/lib/api/types.ts`

前端不只需要补 `intermediate_content`，还需要把后端已经在发送、但当前类型里缺失的 `phase` 一并补上：

```typescript
export type SseEventPhase = {
  type: "phase";
  stage: "reasoning" | "retrieving" | "synthesizing" | string;
};

export type SseEventIntermediateContent = {
  type: "intermediate_content";
  delta: string;
};
```

加入 `SseEvent` 联合类型：

```typescript
export type SseEvent =
  | SseEventStart
  | SseEventPhase
  | SseEventContent
  | SseEventIntermediateContent
  | SseEventThinking
  | SseEventSources
  | SseEventDone
  | SseEventError
  | SseEventHeartbeat
  | SseEventConfirmation
  | SseEventToolCall
  | SseEventToolResult;
```

**约定**：

- `phase` 负责生命周期边界。
- `thinking` 继续负责显示阶段文案。
- 两者不能做同一份状态更新，否则会重复清空或重复触发动画。

### 4.2 扩展 ChatMessage 状态模型

**文件**：`frontend/src/stores/chat-store.ts`

`ChatMessage` 类型新增字段：

```typescript
export type ChatMessage = {
  // ...现有字段不变
  intermediateContent?: string;
  intermediateGeneration?: number;
};
```

这里建议**只扩展类型，不额外给全局 store 增加专门 action**。原因是当前会话消息的真实更新入口在 `useChatSession.ts` 的 `sessionMessagesRef + mutateSessionMessages` 这一层，直接在这里增加局部 helper 更贴合现有架构，也更不容易出现双轨状态不一致。

建议在 `useChatSession.ts` 内新增三个 helper：

```typescript
appendIntermediateContentInSession(sessionId, messageId, delta)
clearIntermediateContentInSession(sessionId, messageId, { bumpGeneration?: boolean })
beginFinalContentInSession(sessionId, messageId, firstDelta)
```

其中：

- `appendIntermediateContentInSession`：累加中间态文本。
- `clearIntermediateContentInSession`：清空中间态；只有“新一轮 reasoning 开始”时才递增 generation。
- `beginFinalContentInSession`：在最终内容第一次到达时，**原子地**清空中间态并写入第一段最终内容，避免每个 content delta 都触发清空和动画。

### 4.3 事件处理逻辑

**文件**：`frontend/src/lib/hooks/useChatSession.ts`

在 `sendMessage()` 的 `onEvent` 回调中新增和调整：

```typescript
if (event.type === "phase") {
  if (activeAssistantIdRef.current && event.stage === "reasoning") {
    clearIntermediateContentInSession(
      sessionId,
      activeAssistantIdRef.current,
      { bumpGeneration: true },
    );
  }
  return;
}

if (event.type === "thinking") {
  if (activeAssistantIdRef.current) {
    updateThinkingStageInSession(sessionId, activeAssistantIdRef.current, event.stage || null);
  }
  return;
}

if (event.type === "intermediate_content") {
  if (activeAssistantIdRef.current) {
    appendIntermediateContentInSession(sessionId, activeAssistantIdRef.current, event.delta);
  }
  return;
}

if (event.type === "content") {
  if (activeAssistantIdRef.current) {
    const message = findMessageInSession(sessionId, activeAssistantIdRef.current);
    if (!message?.content) {
      beginFinalContentInSession(sessionId, activeAssistantIdRef.current, event.delta);
    } else {
      appendMessageContentInSession(sessionId, activeAssistantIdRef.current, event.delta);
    }
  }
  return;
}
```

**生命周期说明**：

| 事件 | 对 intermediateContent 的影响 |
|---|---|
| `phase("reasoning")` 首次 | 通常无影响，因为此时还没有旧中间态 |
| `intermediate_content` | 追加 delta 到 `intermediateContent` |
| `tool_call` | 无影响，中间态与工具步骤并存 |
| `phase("reasoning")` 再次 | 清空旧中间态，并在需要时递增 generation |
| `phase("synthesizing")` | 不清空；等待最终 `content` 首次到来时再切换 |
| `content` 首次 | 原子清空中间态，并写入第一段最终内容 |
| `content` 后续 | 只追加正文，不再重复清空 |
| `done` | 无额外操作 |

### 4.4 消息渲染逻辑修改

**文件**：`frontend/src/components/chat/message-item.tsx`

这部分要同时处理两件事：

1. 继续把“消息内容层”和“活动状态层”拆开，避免又回到三选一。
2. 视觉方向改为更接近 ChatGPT Web：**去掉 AI 头像、去掉 AI 气泡、去掉用户头像；用户消息保留右侧气泡，AI 消息直接渲染在会话内容区。**

也就是说：

- 用户消息：保留右侧气泡，但不显示头像。
- AI 最终消息：不再使用卡片气泡，直接作为正文区块渲染。
- AI 中间态消息：不再使用独立气泡卡片，而是作为同一条 assistant 内容轨道中的“瞬态文本区块”渲染。

#### 判断逻辑

```typescript
const isStreaming = !isUser && message.status === "streaming";

const showFinalContent = !isUser && !!message.content;
const showIntermediateBlock = isStreaming && !message.content && !!message.intermediateContent;
const showExitingIntermediateBlock =
  isStreaming &&
  !message.content &&
  !!message.exitingIntermediateContent;

const hasToolSteps =
  isStreaming &&
  !message.content &&
  !!message.toolSteps &&
  message.toolSteps.length > 0;

const showThinkingIndicator =
  isStreaming &&
  !message.content &&
  !hasToolSteps;
```

#### 渲染结构

```tsx
{isUser ? (
  <div className="user-message-bubble">
    <p>{message.content}</p>
  </div>
) : (
  <>
    {showExitingIntermediateBlock ? (
      <div className="assistant-intermediate assistant-intermediate--exiting">
        <p className="assistant-intermediate-text">{message.exitingIntermediateContent}</p>
      </div>
    ) : null}

    {showIntermediateBlock ? (
      <div className="assistant-intermediate assistant-intermediate--entering" key={message.intermediateGeneration}>
        <p className="assistant-intermediate-text">{message.intermediateContent}</p>
      </div>
    ) : null}

    {showFinalContent ? (
      <div className="assistant-message-body">
        <MarkdownViewer content={message.content} />
      </div>
    ) : null}

    {hasToolSteps ? (
      <ToolStepsIndicator
        steps={message.toolSteps!}
        thinkingStage={message.thinkingStage}
        t={t}
      />
    ) : showThinkingIndicator ? (
      <ThinkingIndicator stage={message.thinkingStage} t={t} />
    ) : null}
  </>
)}
```

**关键点**：

- AI 不再显示头像，也不再包裹最终回答气泡。
- 用户也不显示头像，但继续保留用户气泡。
- 中间态区块和 `ThinkingIndicator` 可以共存。
- 中间态区块和 `ToolStepsIndicator` 也可以共存。
- 中间态与最终回答处于同一 assistant 内容轨道中，切换时不会受气泡边界影响。
- 中间态继续使用纯文本渲染，不做 Markdown 解析。
- 中间态文本不追求“打字机效果”，只做段级切换动画。
- 最终 assistant 正文保留流式输出效果，但不做上弹动画。

### 4.5 动画策略

#### 推荐动画目标

在“AI 无头像、无气泡”的新视觉方向下，可以把中间态动画升级为双槽位切换：

1. 当前中间态在下一段中间态到来前持续显示。
2. 当下一段中间态开始时：
   - 旧中间态进入 `exitingIntermediateContent` 槽位并渐隐上移。
   - 新中间态从 assistant 中间态区域的底部向上弹出。
3. 当最终 content 首次到达时：
   - 当前中间态进入 exiting 槽位并渐隐。
  - 最终 assistant 正文在同一条内容轨道内出现，并直接进入流式输出。

这比“只有淡入”复杂一些，但由于 AI 不再有头像和气泡边界，视觉切换会更自然，复杂度主要增加在状态管理，而不是布局层。

建议样式：

```css
.assistant-intermediate {
  max-width: min(72ch, 100%);
}

.assistant-intermediate--entering {
  animation: intermediate-slide-up-in 0.24s ease-out;
}

.assistant-intermediate--exiting {
  animation: intermediate-fade-up-out 0.22s ease-out forwards;
}

.assistant-intermediate-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: hsl(var(--muted-foreground));
}

@keyframes intermediate-slide-up-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes intermediate-fade-up-out {
  from {
    opacity: 1;
    transform: translateY(0);
  }
  to {
    opacity: 0;
    transform: translateY(-8px);
  }
}
```

#### 状态模型调整

如果采用上面的动画，`ChatMessage` 需要增加一个额外的瞬态字段：

```typescript
exitingIntermediateContent?: string | null;
```

对应 helper 建议调整为：

```typescript
rotateIntermediateContentInSession(sessionId, messageId)
appendIntermediateContentInSession(sessionId, messageId, delta)
beginFinalContentInSession(sessionId, messageId, firstDelta)
clearIntermediateVisualStateInSession(sessionId, messageId)
```

语义如下：

- `rotateIntermediateContentInSession`：把当前 `intermediateContent` 移入 `exitingIntermediateContent`，为下一轮中间态做准备。
- `appendIntermediateContentInSession`：向当前中间态追加 delta。
- `beginFinalContentInSession`：把当前中间态移入 exiting 槽位，同时写入第一段最终内容。
- `clearIntermediateVisualStateInSession`：在动画结束或取消流时彻底清理瞬态字段。

#### generation 的使用边界

`intermediateGeneration` 仍然只在“新一轮中间态块开始渲染”时递增，用来触发 entering 动画。不要在下面两种场景递增：

1. 每次 `intermediate_content` delta 到达。
2. 每次 `content` delta 到达。

否则会带来频繁 remount、动画闪烁和不必要的渲染抖动。

#### 中间态与最终态的输出节奏

这里需要把两类内容区分开：

1. **中间态文本**
  - 不做原生流式打字机效果。
  - 在同一段中间态内部，收到新 delta 时直接更新当前文本内容即可。
  - 视觉重点放在“上一段退出、下一段进入”的段级动画上。

2. **最终 assistant 正文**
  - 保留流式输出的打字机感。
  - 但不要再做上弹或整块进入动画，避免和中间态转场抢戏。
  - 推荐直接按 SSE delta 追加，或做极轻量的帧级合并刷新，不要人为放慢吐字速度。

如果实现时发现某些 provider 会把大量文本一次性塞进单个 delta，可以考虑做一个很轻的 display buffer：

- 目标不是“制造慢速打字机”，而是把大块文本拆成更平滑的显示节奏。
- 刷新周期建议控制在 `16ms ~ 33ms`。
- 不要额外引入肉眼可感知的长延迟。

#### 取消流的行为

本轮已经确认：**用户取消流时，不保留中间态消息。**

因此取消逻辑应直接清理：

- `intermediateContent`
- `exitingIntermediateContent`
- `thinkingStage`
- 流式状态标记

---

## 五、边界情况处理

| 场景 | 处理方式 |
|---|---|
| LLM 未返回中间态文本（包括直接回答场景） | `intermediateContent` 始终为空，UI 自动回退到现有 ThinkingIndicator 或 ToolStepsIndicator |
| 中间态存在但尚未进入 tool_call | assistant 中间态区块与 ThinkingIndicator 共存 |
| 中间态存在且已进入 tool_call | assistant 中间态区块与 ToolStepsIndicator 共存 |
| 快速连续多轮 reasoning | 下一轮 reasoning 到达时，旧中间态进入 exiting 槽位，新中间态进入当前槽位 |
| 最终 content 分多段到达 | 只在第一段最终 content 到达时把当前中间态转入 exiting 槽位，后续 delta 只追加正文 |
| `phase` 和 `thinking` 同时到达 | 只让 `phase` 处理生命周期，`thinking` 只更新阶段文案，避免双重清理 |
| 页面刷新 / 历史消息加载 | `intermediateContent` 不持久化，只显示终结态历史消息 |
| 用户取消流式请求 | 直接清理中间态与 exiting 槽位，不保留取消前的中间态文本 |

### 5.1 当前 provider 实测结论

截至 2026-04-07，真实探针结果表明：

1. 默认 `qwen3.5-plus` 路径下，tool_call 场景通常只有 structured tool_calls，没有自然语言中间态 content。
2. `glm-5` 路径下，tool_call 场景会先返回自然语言中间态 content，再返回 tool_call。

当前产品默认体验按 `glm-5` 路径设计和优化，`qwen3.5-plus` 视为兼容性回退路径。

因此前端实现时必须假设：

- 中间态 UI 是“能力增强”，不是“每次都出现”的固定体验。
- ThinkingIndicator / ToolStepsIndicator 的无中间态回退路径必须长期保留。

---

## 六、受影响的文件清单

| 文件 | 改动描述 |
|---|---|
| `frontend/src/lib/api/types.ts` | 新增 `SseEventPhase`、`SseEventIntermediateContent` 类型，扩展 `SseEvent` 联合 |
| `frontend/src/stores/chat-store.ts` | `ChatMessage` 新增 `intermediateContent`、`exitingIntermediateContent`、`intermediateGeneration` 字段 |
| `frontend/src/lib/hooks/useChatSession.ts` | 增加中间态轮换与清理 helper；处理 `phase`、`intermediate_content`、最终 content 首段切换与取消清理 |
| `frontend/src/components/chat/message-item.tsx` | 去掉 AI 头像与 AI 气泡；去掉用户头像；保留用户气泡；支持 assistant 中间态 entering/exiting 区块 |
| `frontend/src/styles/thinking-indicator.css` 或相邻样式文件 | 新增中间态气泡样式和淡入动画 |

### 原则上无需修改的文件

| 文件 | 原因 |
|---|---|
| `frontend/src/lib/api/chat.ts` | SSE 解析入口保持通用 |
| `frontend/src/lib/utils/sse-parser.ts` | 解析器不关心具体事件类型 |
| `frontend/src/app/api/v1/.../route.ts` | Next.js 代理层是透传管道 |
| `frontend/src/components/chat/chat-panel.tsx` | 列表渲染仍由 `MessageItem` 负责 |

---

## 七、测试计划

### 7.1 组件测试

| 测试文件 | 覆盖内容 |
|---|---|
| `frontend/tests/components/chat/message-item.intermediate.test.tsx` | 中间态气泡与 ThinkingIndicator 共存；与 ToolStepsIndicator 共存；最终 content 到达后中间态不再渲染 |

### 7.2 Hook 测试

| 测试文件 | 覆盖内容 |
|---|---|
| `frontend/tests/lib/hooks/useChatSession.intermediate.test.tsx` | `intermediate_content` 事件正确追加；`phase("reasoning")` 清空旧中间态；首个 `content` delta 原子切换；后续 content delta 不重复清理 |

### 7.3 状态测试

| 测试文件 | 覆盖内容 |
|---|---|
| `frontend/tests/lib/hooks/useChatSession.phase-thinking.test.tsx` | `phase` 与 `thinking` 双事件不会造成重复清空或重复动画 |

---

## 八、与后端的配合边界

| 职责 | 后端 | 前端 |
|---|---|---|
| 中间态文本产生 | `_stream_reasoning()` 从 LLM 流中提取 content delta | 无需感知 |
| 中间态事件传递 | SSE `intermediate_content` 事件 | 追加到 `intermediateContent` |
| 生命周期边界 | 发出 `phase` 与 `thinking` | 只让 `phase` 控制生命周期，`thinking` 仅更新标签 |
| 终结态到达 | `ContentEvent` 传递最终回答 | 在首个 final delta 时清理中间态并切换正文 |
| 中间态持久化 | 后端仅在 structured tool_call 场景保留自然语言 content | 前端 `intermediateContent` 始终视为瞬态字段 |

---

## 九、待确认事项

1. 是否接受最终正文使用“自然流式追加或极轻量帧级缓冲”的打字机效果，而不是人为减速的字符动画。当前建议接受。
2. 中间态文本是否坚持纯文本渲染。如果后续希望支持 Markdown，需要再评估增量渲染性能和闪烁问题。
3. 是否明确约定：前端生命周期只消费 `phase`，不在 `thinking` 分支里做清理逻辑。这一点需要前后端一起定死，避免后续维护时再引入重复更新。
4. 是否接受为 entering/exiting 动画增加一个 `exitingIntermediateContent` 瞬态字段。当前建议接受，因为这能显著提升转场质量。
