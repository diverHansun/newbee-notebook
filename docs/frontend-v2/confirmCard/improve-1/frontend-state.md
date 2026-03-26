# 前端类型定义与状态管理

## 概述

本文档定义前端的类型变更和状态流转逻辑。核心改动是在 `PendingConfirmation` 中新增 `actionType`、`targetType` 字段, 以及 `collapsed` 状态。

## 类型定义

### SSE 事件类型 (types.ts)

```typescript
export type SseEventConfirmation = {
  type: "confirmation_request";
  request_id: string;
  tool_name: string;
  action_type: "create" | "update" | "delete" | "confirm";
  target_type: "note" | "diagram" | "document";
  args_summary: Record<string, unknown>;
  description: string;
};
```

新增 `action_type` 和 `target_type` 两个字段, 由后端结构化提供。

### PendingConfirmation (chat-store.ts)

```typescript
export type ConfirmationActionType = "create" | "update" | "delete" | "confirm";
export type ConfirmationTargetType = "note" | "diagram" | "document";
export type ConfirmationStatus =
  | "pending"
  | "confirmed"
  | "rejected"
  | "timeout"
  | "collapsed";

export type PendingConfirmation = {
  requestId: string;
  toolName: string;
  actionType: ConfirmationActionType;
  targetType: ConfirmationTargetType;
  argsSummary: Record<string, unknown>;
  description: string;
  status: ConfirmationStatus;
  expiresAt: number;
  resolvedFrom?: "confirmed" | "rejected" | "timeout";
};
```

变更点:
- 新增 `actionType` 和 `targetType`
- `status` 新增 `"collapsed"` 值
- 新增 `resolvedFrom` 可选字段, 在 collapsed 状态下记录折叠前的最终结果 (confirmed/rejected/timeout), 供内联标签渲染正确图标和文案

## 状态流转

```
            用户确认
pending ──────────────> confirmed ──(1.5s)──> collapsed
   |                                             ^
   |     用户拒绝                                |
   +────────────────> rejected ───(1.5s)─────────+
   |                                             |
   |     超时 (180s)                             |
   +────────────────> timeout ────(1.5s)─────────+
```

### 各状态说明

| 状态 | 含义 | 渲染 |
|------|------|------|
| `pending` | 等待用户操作 | 完整卡片 + 倒计时 + 按钮 |
| `confirmed` | 用户已确认 | 卡片 + "已确认" badge, 无按钮, 开始 fade out |
| `rejected` | 用户已拒绝 | 卡片 + "已拒绝" badge, 无按钮, 开始 fade out |
| `timeout` | 超时自动拒绝 | 卡片 + "已超时" badge, 无按钮, 开始 fade out |
| `collapsed` | 最终状态 | 内联标签 (不可逆) |

## 状态管理实现

### trackPendingConfirmation 修改 (useChatSession.ts)

在收到 `confirmation_request` SSE 事件时, 从事件中提取新字段:

```typescript
const pendingConfirmation: PendingConfirmation = {
  requestId: event.request_id,
  toolName: event.tool_name,
  actionType: event.action_type,
  targetType: event.target_type,
  argsSummary: event.args_summary,
  description: event.description,
  status: "pending",
  expiresAt: Date.now() + CONFIRMATION_TIMEOUT_MS,
};
```

### resolveConfirmation 修改 (useChatSession.ts)

确认/拒绝后, 先设置中间状态, 然后 1.5 秒后推进到 collapsed:

```typescript
const resolveConfirmation = useCallback(
  async (requestId: string, approved: boolean) => {
    const sessionId = currentSessionId;
    if (!sessionId) return;

    const message = findMessageByConfirmationRequest(requestId);
    if (!message?.pendingConfirmation) return;

    clearConfirmationTimer(requestId);

    // 1. 设置中间状态 (confirmed / rejected)
    updateMessage(message.id, {
      pendingConfirmation: {
        ...message.pendingConfirmation,
        status: approved ? "confirmed" : "rejected",
      },
    });

    // 2. 1.5 秒后折叠
    window.setTimeout(() => {
      const msg = findMessageByConfirmationRequest(requestId);
      if (msg?.pendingConfirmation && msg.pendingConfirmation.status !== "pending") {
        updateMessage(msg.id, {
          pendingConfirmation: { ...msg.pendingConfirmation, status: "collapsed" },
        });
      }
    }, 1500);

    // 3. 通知后端
    await confirmChatAction(sessionId, {
      request_id: requestId,
      approved,
    });
  },
  [clearConfirmationTimer, currentSessionId, findMessageByConfirmationRequest, updateMessage]
);
```

### timeout 处理修改

超时回调中同样增加 1.5 秒后折叠逻辑:

```typescript
// 原有: 直接设置 timeout 状态
updateMessage(message.id, {
  pendingConfirmation: {
    ...message.pendingConfirmation,
    status: "timeout",
  },
});

// 新增: 1.5 秒后折叠
window.setTimeout(() => {
  const msg = findMessageByConfirmationRequest(event.request_id);
  if (msg?.pendingConfirmation && msg.pendingConfirmation.status === "timeout") {
    updateMessage(msg.id, {
      pendingConfirmation: { ...msg.pendingConfirmation, status: "collapsed" },
    });
  }
}, 1500);
```

## 页面刷新恢复

由于 `collapsed` 是持久化状态 (存在 store 中), 页面刷新后:
- `collapsed` 状态直接渲染为内联标签
- `pending` 状态如果已过期 (expiresAt < Date.now()), 应在组件挂载时自动推进到 `timeout` -> `collapsed`
- `confirmed` / `rejected` / `timeout` 中间状态直接推进到 `collapsed` (补偿刷新期间未完成的动画)
