# P5: UI 打磨（输入框高度 + 用户气泡颜色 + 消息自动滚动）

## 问题描述

1. **输入框过高**：`chat-input-container` 的 textarea 无最大高度限制，输入区占据过多垂直空间，消息列表显示面积被压缩
2. **用户气泡颜色不合理**：当前用户气泡背景为 `hsl(var(--primary))`（深色近黑），与 AI 气泡对比度不足，且视觉偏沉
3. **无自动滚动**：用户发送消息或 AI 开始回复时，消息列表不自动滚到底部，用户需要手动下滚

## 当前实现

### 输入框（globals.css / chat.css 拆分后）

```css
.chat-input-textarea {
  /* 无 max-height 限制 */
  resize: none;
  min-height: 60px;
}
```

### 用户气泡（message-item.tsx）

```tsx
background: isUser ? "hsl(var(--primary))" : "hsl(var(--card))"
color:      isUser ? "hsl(var(--primary-foreground))" : "hsl(var(--card-foreground))"
```

### 自动滚动（chat-panel.tsx）

当前无任何 `scrollIntoView` 或 `scrollTop` 相关逻辑。

## 设计方案

### 1. 输入框高度约束

在 CSS（P1 拆分后对应 `chat.css`）中为 textarea 添加最大高度：

```css
.chat-input-textarea {
  resize: none;
  min-height: 60px;
  max-height: 120px;    /* 约 5 行，超出后内部滚动 */
  overflow-y: auto;
}
```

同时确认消息列表容器已正确设置：

```css
.chat-message-list {
  flex: 1 1 0;
  min-height: 0;     /* flex 子元素必须设置，否则无法触发 overflow */
  overflow-y: auto;
}
```

输入区 wrapper 需加 `flex-shrink: 0`，防止消息列表被压缩时输入区跟着收缩。

### 2. 用户气泡颜色

> **Improve-4 范围**：仅支持亮色模式（Light Mode），暗色模式支持留待后续阶段。

在 `globals.css`（CSS 变量节）新增两个亮色主题变量：

```css
:root {
  /* 用户消息气泡（淡蓝，亮色模式专用） */
  --user-bubble-bg: 214 89% 94%;    /* sky-100 近似，#DBEAFE */
  --user-bubble-fg: 213 94% 22%;    /* 深蓝文字 #1e40af，满足 WCAG AA 4.5:1 */
}
```

在 `message-item.tsx` 中将用户气泡的内联 `background`/`color` 改为引用 CSS 变量：

```tsx
// 修改前
background: "hsl(var(--primary))"   // 深色近黑
color:      "hsl(var(--primary-foreground))"

// 修改后
background: "hsl(var(--user-bubble-bg))"
color:      "hsl(var(--user-bubble-fg))"
```

CSS 变量方式的好处：后续需要调整颜色时只改 `globals.css` 一处，组件不参与。

### 3. 消息自动滚动

#### 设计原则

**核心行为**：消息列表始终跟随内容增长自动滚动到底部；仅当用户主动向上拖动滚动条时，暂停自动滚动；用户重新滚到接近底部时，自动滚动立即恢复。

不设置"新消息"浮动提示按钮，保持界面简洁——用户滚下来即可看到新内容，不需要额外操作指引。

#### 触发场景与行为

| 触发场景 | 行为 |
|---------|------|
| 用户点击发送（消息添加到列表） | 立即滚到底部，无论当前 `isNearBottom` 状态如何 |
| AI 回复消息添加（`messages.length` 增加） | 立即滚到底部，无论当前状态 |
| streaming 过程中 content 更新 | 若 `isNearBottom === true`，随 `requestAnimationFrame` 持续跟随滚动 |
| 用户手动上滚（距底部 > 100px） | `isNearBottom` 置为 false，暂停流式跟随滚动 |
| 用户手动下滚回近底部（距底部 ≤ 100px） | `isNearBottom` 置为 true，流式跟随立即恢复 |
| streaming 结束 | 若 `isNearBottom === false`，不强制滚动 |

#### 实现要点（chat-panel.tsx）

**锚点元素**（已存在的 `messagesEndRef`）：

```tsx
<div ref={messagesEndRef} style={{ height: 0 }} aria-hidden />
```

**`isNearBottom` 判断**（用 `useRef` 存储避免 re-render）：

```tsx
const isNearBottomRef = useRef(true);

function handleScroll(e: React.UIEvent<HTMLDivElement>) {
  const el = e.currentTarget;
  isNearBottomRef.current =
    el.scrollHeight - el.scrollTop - el.clientHeight <= 100;
}
```

**Effect 1 — 新消息/发送时立即滚**（`messages.length` 变化时，不判断 `isNearBottom`，始终滚动）：

```tsx
useEffect(() => {
  messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
}, [messages.length]);
```

**Effect 2 — streaming 同步跟随**（使用 `requestAnimationFrame`，每帧检查并滚动）：

```tsx
useEffect(() => {
  if (!isStreaming) return;

  let rafId: number;

  function syncScroll() {
    if (isNearBottomRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: "instant" });
    }
    rafId = requestAnimationFrame(syncScroll);
  }

  rafId = requestAnimationFrame(syncScroll);
  return () => cancelAnimationFrame(rafId);
}, [isStreaming]);
```

> **`behavior: "instant"` vs `"smooth"`**：Effect 1（新消息到来）用 `smooth` 提供过渡感；Effect 2（streaming 跟随）用 `instant`，避免每帧都触发 smooth 动画互相叠加造成抖动。

**Effect 3 — 会话切换/历史加载完成后滚到底部**（监听 `sessionId` 变化）：

当前行为：用户切换会话后，消息列表默认停在顶部，需手动下滚才能看到最新内容，体验较差。

```tsx
// 从 chat-store 或 props 读取当前 sessionId
useEffect(() => {
  // messages 加载完成后执行一次，不判断 isNearBottom（切换会话时无论在哪都应跳到底部）
  if (messages.length > 0) {
    messagesEndRef.current?.scrollIntoView({ behavior: "instant" });
  }
}, [sessionId]);  // 仅监听 sessionId 变化，不监听 messages
```

> 用 `"instant"` 而非 `"smooth"`：会话切换是场景跳转，不是连续滚动，即时定位更符合认知。若 `messages` 异步加载有延迟，可在 `useEffect` 内增加 `setTimeout(fn, 0)` 等待一帧后再滚。

### 实现补充（2026-02-23）

在实际页面中，历史消息（尤其 markdown/表格内容）会在初次渲染后继续扩展高度，单次 `setTimeout(0)` 滚到底部容易“停在中间”。实现中已改为：

- 会话切换 / 历史加载阶段使用短时 `requestAnimationFrame` 追踪（约 600ms 上限）
- 每帧检查“距底部距离”，稳定到近底部后停止追踪

这样可显著降低“刷新后仍停在半屏位置”的概率，且不会长期占用动画帧循环。

#### 滚动容器要求

消息列表容器需确保：

```css
.chat-message-list {
  flex: 1 1 0;
  min-height: 0;     /* flex 子元素必须设置，否则 overflow 无法触发 */
  overflow-y: auto;
}
```

输入区 wrapper 加 `flex-shrink: 0`，防止消息列表被压缩时输入区一起收缩。

## 涉及文件

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/app/globals.css`（P1 后对应 `styles/chat.css`） | textarea `max-height: 120px`；消息列表 `min-height: 0`；输入区 `flex-shrink: 0` |
| `frontend/src/app/globals.css`（CSS 变量节） | 新增 `--user-bubble-bg`、`--user-bubble-fg`（亮色模式） |
| `frontend/src/components/chat/message-item.tsx` | 用户气泡改用 CSS 变量 |
| `frontend/src/components/chat/chat-panel.tsx` | 自动滚动逻辑（Effect 1 + Effect 2 + Effect 3 + `onScroll` 处理器） |

## 验证标准

### 输入框

- 输入框空白时高度约 56px（单行 + padding）
- 输入多行文字后最大扩展到约 120px（5 行），不继续增高
- 超出 5 行时 textarea 内部出现滚动条，整体布局不跳动
- 消息列表高度不因输入框高度变化而出现跳动

### 用户气泡

- 用户气泡背景为淡蓝色（sky-100，`#DBEAFE` 近似）
- 文字颜色与背景对比度满足 WCAG AA（≥ 4.5:1）
- AI 气泡颜色、布局不受影响

### 自动滚动

- 用户发送消息后，视图 smooth 滚动到当前消息位置
- AI 回复开始（新消息加入列表）时，视图 smooth 滚动到底部
- streaming 过程中，消息列表随内容增长持续跟随滚动（instant，无抖动）
- 用户在 streaming 过程中手动上滚后，streaming 跟随停止，历史内容可正常浏览
- 用户手动下滚回近底部（≤ 100px）后，streaming 跟随立即自动恢复
- streaming 结束后，若用户仍在历史位置，不强制跳回底部（不干扰阅读）

### 会话切换

- 切换到另一会话后，消息列表立即定位到该会话的最新消息（底部），不停在顶部
- 若新会话消息列表为空，不触发滚动（无行为）
- 切换后继续发消息，Effect 1 / Effect 2 正常工作，不受影响

### 回归补充（2026-02-23）

- 已验证：刷新页面后历史消息列表可定位到底部（此前存在停在中段的问题，已修复）
- 已验证：发送新消息后自动滚动保持在底部附近（`distanceFromBottom` 接近 0）
