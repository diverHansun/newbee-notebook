# P2: AI 思考指示器

## 问题描述

当用户发送消息后，前端立即创建一个空的 assistant 消息（`useChatSession.ts` 第 292 行），在后端完成 RAG 检索、Tool 调用、LLM 首 token 生成之前（可能 5-30 秒），页面上会出现一个空白的消息气泡，视觉上非常突兀。

当前仅在消息顶部显示一个 11px 的"生成中..."文字（`message-item.tsx` 第 71 行），辨识度低且缺乏反馈感。

## 根因

`useChatSession.ts` 的消息创建流程：

```
用户点击发送
  -> addMessage(user message, status: "done")
  -> addMessage(assistant message, content: "", status: "streaming")  // 空气泡出现
  -> 调用 chatStream()
  -> 等待后端 "start" 事件
  -> 等待后端 "content" 事件  // 此时才有内容填入气泡
```

从空气泡出现到首个 content 到达之间，没有任何视觉指示。

## 设计方案

### 1. 前端：ThinkingIndicator 组件

在 `message-item.tsx` 中，当 `status === "streaming" && !content` 时，替换空气泡为紧凑型思考指示器。

#### 视觉规格

```
┌────────────────────────────────────┐
│  [o]  AI 正在思考...               │   高度: ~40px
│  ━━━━━━━━░░░░░░░░░░░░░░░░░░░░░░  │   宽度: 自适应，max-width 240px
└────────────────────────────────────┘
```

- 旋转渐变环：16x16px，使用 `conic-gradient` 实现 bee-yellow 到 bee-amber 的渐变，`animation: spin 1s linear infinite`
- 阶段文字：12px，`color: hsl(var(--muted-foreground))`，单行
- 脉冲进度条：高度 2px，宽度 100%，使用 `shimmer` 动画（线性渐变从左到右滑动）
- 容器：`background: hsl(var(--muted) / 0.5)`，`border: 1px solid hsl(var(--border))`，`border-radius: 8px`，`padding: 10px 14px`
- 不使用 `.card` 样式，保持轻量

#### 过渡动画

当首个 `content` chunk 到达时（`message.content` 从空变为非空），ThinkingIndicator 以 `opacity: 0` + `transform: translateY(-4px)` 过渡消失（300ms），消息气泡以 `opacity: 1` 淡入。

#### 阶段文字映射

| stage 值 | 显示文字 |
|----------|----------|
| `"retrieving"` | 正在检索知识库... |
| `"searching"` | 正在搜索相关内容... |
| `"generating"` | 正在生成回答... |
| 默认 / 无 stage | AI 正在思考... |

文字写入 `lib/i18n/strings.ts`，同时提供英文版本，为 improve-4 做准备。

### 2. 后端：新增 thinking SSE 事件类型

#### SSEEvent 扩展

在 `api/routers/chat.py` 的 `SSEEvent` 类中新增：

```python
@staticmethod
def thinking(stage: str = "thinking") -> str:
    return SSEEvent.format({"type": "thinking", "stage": stage})
```

#### chat_service.py 事件注入

在 `chat_stream()` 方法中，`start` 事件之后、进入 mode stream 循环之前：

```python
yield {"type": "start", "message_id": message_id}
yield {"type": "thinking", "stage": "retrieving"}   # 新增

# ... 进入 mode.stream() 获取 content chunks ...

# 在 mode.stream() 内部，首个 content 到达前可选：
yield {"type": "thinking", "stage": "generating"}    # 新增
```

具体的 thinking 事件发送时机取决于 P4 的两阶段流式架构（详见 P4 文档），此处定义事件格式和前端处理逻辑。

#### 事件类型层设施

`thinking` 是新增的 SSE 事件类型，需要在两处注册：

1. **类型定义**：在 `frontend/src/lib/api/types.ts` 的 `SseEvent` 联合类型中新增 `thinking` 分支（`{ type: "thinking"; stage: string }`）。SSE 流的实际解析在 `lib/utils/sse-parser.ts`，它将任意事件转发给调用方，无需修改解析逻辑本身。

2. **业务处理落点**：`thinking` 事件的响应逻辑应在 `useChatSession` 中处理（而非 `useChatStream`）。原因：`useChatStream` 只是流生命周期封装，不持有当前 assistant 消息 ID；`useChatSession` 持有 `activeAssistantIdRef`，能直接定位到需要更新的消息对象。

```typescript
// useChatSession.ts 中处理 thinking 事件
if (event.type === "thinking") {
  updateThinkingStage(activeAssistantIdRef.current, event.stage);
  return;
}
```

收到 `content` 事件时自动清除 thinking 状态。

### 3. Store 扩展

`chat-store.ts` 的 `ChatMessage` 类型新增可选字段：

```typescript
thinkingStage?: string | null;  // "retrieving" | "searching" | "generating" | null
```

新增 action：

```typescript
updateThinkingStage: (id: string, stage: string | null) => void;
```

在 `appendMessageContent` 中自动将 `thinkingStage` 置为 `null`。

### 4. CSS 动画

在 `globals.css` 中新增：

```css
/* 思考指示器 */
.thinking-indicator { ... }

@keyframes thinking-spin {
  to { transform: rotate(360deg); }
}

@keyframes thinking-shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

@keyframes thinking-fade-out {
  to { opacity: 0; transform: translateY(-4px); }
}
```

## 涉及文件

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/lib/api/types.ts` | `SseEvent` 联合类型新增 `thinking` 分支 |
| `frontend/src/components/chat/message-item.tsx` | 条件渲染 ThinkingIndicator |
| `frontend/src/stores/chat-store.ts` | 新增 thinkingStage 字段和 action |
| `frontend/src/lib/hooks/useChatSession.ts` | 处理 thinking 事件，更新 thinkingStage |
| `frontend/src/lib/hooks/useChatStream.ts` | 将 thinking 事件透传给 useChatSession 回调 |
| `frontend/src/app/globals.css` | 指示器样式和动画 |
| `frontend/src/lib/i18n/strings.ts` | 新增，阶段文字常量 |
| `newbee_notebook/api/routers/chat.py` | SSEEvent.thinking() |
| `newbee_notebook/application/services/chat_service.py` | yield thinking 事件 |

## 验证标准

- 发送消息后，空气泡不再出现，取而代之的是紧凑型思考指示器
- 指示器显示旋转渐变环 + 阶段文字 + 脉冲进度条
- 后端 thinking 事件到达时，阶段文字实时更新
- 首个 content chunk 到达后，指示器平滑消失，消息气泡淡入
- 指示器整体高度不超过 50px，视觉简洁
- **超时降级**：若 30 秒内未收到任何 `content` 事件（网络超时或后端异常），前端自动将 `thinkingStage` 置为 `null`，指示器消失，不无限等待。具体超时逻辑在 `useChatSession.ts` 中通过 `setTimeout` + 清理函数实现（`useChatStream.ts` 仅负责流生命周期封装）。
- **取消交互补充（回归修复）**：用户主动取消流式时，不显示原始内部状态字符串 `cancelled`。若 assistant 仍为空占位消息则直接移除；若已有部分内容，则状态文案显示为本地化文本（如“已取消”）。

> P4 实现后，`thinking(searching)` 和 `thinking(generating)` 两个阶段都会在正确时机推送，本文档定义的各阶段文字映射将得到充分利用。
