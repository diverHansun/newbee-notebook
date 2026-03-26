# 组件重设计与 i18n 策略

## 概述

本文档定义 ConfirmationCard 组件的重构方案, 包括 i18n 文案拼装、组件拆分、渲染逻辑和信息展示优化。

## i18n 文案策略

### 核心函数: confirmationTitle

根据 `actionType` 和 `targetType` 拼装本地化标题:

```typescript
function confirmationTitle(
  actionType: ConfirmationActionType,
  targetType: ConfirmationTargetType,
  t: TranslateFn
): string {
  const key = uiStrings.confirmation.actionTitle?.[actionType]?.[targetType];
  if (key) return t(key);
  // 回退: 用已有的通用翻译
  return `${t(uiStrings.confirmation.title)}`;
}
```

### strings.ts 新增内容

```typescript
confirmation: {
  // ... 保留现有字段 ...
  actionTitle: {
    create: {
      note: { zh: "创建笔记", en: "Create note" },
      diagram: { zh: "创建图表", en: "Create diagram" },
      document: { zh: "关联文档", en: "Link document" },
    },
    update: {
      note: { zh: "更新笔记", en: "Update note" },
      diagram: { zh: "更新图表", en: "Update diagram" },
      document: { zh: "更新文档", en: "Update document" },
    },
    delete: {
      note: { zh: "删除笔记", en: "Delete note" },
      diagram: { zh: "删除图表", en: "Delete diagram" },
      document: { zh: "解除文档关联", en: "Unlink document" },
    },
    confirm: {
      note: { zh: "确认笔记操作", en: "Confirm note action" },
      diagram: { zh: "确认图表类型", en: "Confirm diagram type" },
      document: { zh: "确认文档操作", en: "Confirm document action" },
    },
  },
  // 按钮文案 (区分操作类型)
  confirmDelete: { zh: "确认删除", en: "Confirm delete" },
  // 内联标签动词
  actionConfirmed: { zh: "已确认", en: "Confirmed" },
  actionRejected: { zh: "已拒绝", en: "Rejected" },
  actionTimeout: { zh: "已超时", en: "Timed out" },
}
```

## 组件拆分

### 渲染逻辑 (message-item.tsx)

```tsx
{!isUser && message.pendingConfirmation ? (
  message.pendingConfirmation.status === "collapsed" ? (
    <ConfirmationInlineTag
      confirmation={message.pendingConfirmation}
    />
  ) : (
    <ConfirmationCard
      confirmation={message.pendingConfirmation}
      onConfirm={() => onResolveConfirmation?.(
        message.pendingConfirmation!.requestId, true
      )}
      onReject={() => onResolveConfirmation?.(
        message.pendingConfirmation!.requestId, false
      )}
    />
  )
) : null}
```

### ConfirmationCard 组件重构

核心变更:

1. 标题改用 `confirmationTitle()` 生成本地化文案
2. 隐藏 requestId, 不再显示
3. 工具名改用 i18n 映射 (复用 progress-bar 的 `toolDisplayLabel`)
4. 根据 `actionType` 设置 `data-action-type` 属性, 驱动 CSS 样式
5. 根据 `status` 设置 CSS 类, 驱动动画

```tsx
export function ConfirmationCard({
  confirmation,
  onConfirm,
  onReject,
}: ConfirmationCardProps) {
  const { t } = useLang();
  const summaryEntries = useMemo(
    () => Object.entries(confirmation.argsSummary ?? {}),
    [confirmation.argsSummary]
  );
  const isPending = confirmation.status === "pending";
  const isResolving = ["confirmed", "rejected", "timeout"].includes(
    confirmation.status
  );
  const title = confirmationTitle(
    confirmation.actionType,
    confirmation.targetType,
    t
  );
  const statusBadge = !isPending ? statusLabel(confirmation.status, t) : null;
  const isDestructive = confirmation.actionType === "delete";

  return (
    <div
      className={`confirmation-card ${
        isResolving ? "confirmation-card--resolving" : "confirmation-card--pending"
      }`}
      data-action-type={confirmation.actionType}
      data-confirmation-status={confirmation.status}
    >
      <div className="confirmation-card-header">
        <strong>{title}</strong>
        {statusBadge ? (
          <span className="badge badge-default">{statusBadge}</span>
        ) : null}
      </div>

      {/* 仅显示关键参数摘要, 不显示 requestId */}
      {summaryEntries.length > 0 ? (
        <dl className="confirmation-card-summary">
          {summaryEntries.map(([key, value]) => (
            <div key={key} className="confirmation-card-summary-row">
              <dt>{key}</dt>
              <dd>{formatSummaryValue(value)}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {isPending ? (
        <div className="confirmation-card-actions">
          <button
            className={`btn btn-sm ${isDestructive ? "btn-destructive" : ""}`}
            type="button"
            onClick={onConfirm}
          >
            {isDestructive
              ? t(uiStrings.confirmation.confirmDelete)
              : t(uiStrings.confirmation.confirm)}
          </button>
          <button
            className="btn btn-ghost btn-sm"
            type="button"
            onClick={onReject}
          >
            {t(uiStrings.confirmation.reject)}
          </button>
        </div>
      ) : null}
    </div>
  );
}
```

### ConfirmationInlineTag 组件

collapsed 状态下渲染的内联标签:

```tsx
function ConfirmationInlineTag({
  confirmation,
}: {
  confirmation: PendingConfirmation;
}) {
  const { t } = useLang();
  const title = confirmationTitle(
    confirmation.actionType,
    confirmation.targetType,
    t
  );
  const resolvedStatus = confirmation.resolvedFrom ?? "confirmed";

  // 根据最终结果选择图标和文案
  const icon = resolvedStatus === "rejected" || resolvedStatus === "timeout"
    ? "\u2715" : "\u2713";
  const verb = statusLabel(resolvedStatus, t)
    || t(uiStrings.confirmation.actionConfirmed);

  return (
    <span
      className="confirmation-inline-tag"
      data-status={resolvedStatus}
    >
      {icon} {verb} -- {title}
    </span>
  );
}
```

注意: collapsed 状态需要保留原始的 resolved 状态 (confirmed/rejected/timeout), 以便内联标签显示正确的图标和文案。

### collapsed 状态记录原始结果

在推进到 collapsed 时, 将原始 status 记录到 `resolvedFrom` 字段:

```typescript
// PendingConfirmation 类型新增:
resolvedFrom?: "confirmed" | "rejected" | "timeout";
```

折叠时赋值:

```typescript
updateMessage(msg.id, {
  pendingConfirmation: {
    ...msg.pendingConfirmation,
    status: "collapsed",
    resolvedFrom: msg.pendingConfirmation.status as "confirmed" | "rejected" | "timeout",
  },
});
```

内联标签读取 `resolvedFrom`:

```tsx
const resolvedStatus = confirmation.resolvedFrom ?? "confirmed";
```

## 信息展示对比

### 改造前

```
+-------------------------------------------+
| 确认操作                        [已确认]    |
| Update note metadata.                      |
| 剩余时间    02:45                          |
| 请求 ID     req-uuid-xxx                   |
| 工具        update_note                    |
| note_id     note-1                         |
|                                            |
|  [确认]  [拒绝]                            |
+-------------------------------------------+
```

### 改造后 (pending, 非危险操作)

```
+-------------------------------------------+
| 更新笔记                                   |
| note_id     note-1                         |
|                                            |
|  [确认]  [拒绝]                            |
+-------------------------------------------+
```

### 改造后 (pending, 危险操作)

```
+-------------------------------------------+  <-- 红色边框
| 删除图表                                   |
| diagram_id  d-123                          |
|                                            |
|  [确认删除]  [拒绝]                         |  <-- 红色确认按钮
+-------------------------------------------+
```

### 改造后 (collapsed, 内联标签)

```
v 已确认 -- 更新笔记
```
