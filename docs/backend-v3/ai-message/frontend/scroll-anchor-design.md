# 发送消息后滚动锚定设计

## 概述

本文档描述用户发送消息后的滚动行为优化。核心目标：

- 用户发送消息后，将该条用户消息锚定到消息区的“自然顶部留白”位置，而不是消息区最底部。
- AI spinner / 工具状态出现在用户消息正下方。
- AI 正文开始流式输出后，不再把视口强行拉回底部，避免“首拍正确，后续回弹”。

与已有文档的关系：

- `assistant-message-layout-plan.md`：定义消息视觉布局。
- `spinner-animation-design.md`：定义 spinner / 工具状态动效。
- 本文档：定义发送消息后的滚动位置策略。

---

## 一、问题描述

当前行为分成两个阶段：

1. 用户发送后，首拍锚定可以生效，用户消息会短暂上移。
2. AI 中间态或正文开始后，现有的“near-bottom 持续跟随”逻辑又会执行 `block: "end"` 的滚动，把视口重新拉回底部。

结果就是：

- 用户感觉“发送后锚定没有真正生效”。
- 用户消息和 AI 状态仍然挤在消息区底部。
- 发送后获得的空间层次感被后续滚动策略冲掉。

---

## 二、设计目标

1. **自然顶部锚定**
   用户消息不应贴到消息区边框最上方，而应对齐消息列表原本的顶部留白。

2. **发送态与跟随态分离**
   “发送后锚定”与“底部 near-bottom 跟随”是两种不同策略，不能共用同一套滚动控制。

3. **短回复不回弹**
   即使 AI 回复很短，也不应该因为正文开始就把用户消息拉回到底部附近。

4. **主动交互不误判**
   当前版本优先保证锚定稳定，不再让普通 `scroll` 事件直接结束锚定，避免程序滚动和布局回流被误判成用户操作。

5. **会话切换保持原行为**
   切换 session 时仍使用原来的 settle-to-bottom 逻辑。

---

## 三、实现方案

### 3.1 总体方案

采用“滚动状态机 + spacer / sentinel 分离”的方案。

不再让同一个底部元素同时承担两件事：

- `bottomSpacer`：只负责临时撑高列表，保证用户消息能停在目标位置。
- `endSentinel`：只负责 session settle 与 near-bottom follow 的“滚到底部”目标。

### 3.2 顶部锚定位置

锚定目标不是“容器绝对顶部”，而是消息列表的自然顶部留白。

具体做法：

```tsx
const topInset = parseFloat(window.getComputedStyle(messageListRef.current).paddingTop) || 0;
const desiredScrollTop = target.offsetTop - topInset;
```

当前 `chat-message-list` 的顶部内边距为 `16px`，因此发送后的用户消息应与“滚到最前面时第一条消息”的自然位置一致。

### 3.3 新增状态与引用

```tsx
const [bottomPadding, setBottomPadding] = useState(0);
const [scrollMode, setScrollMode] = useState<ScrollMode>("stream-follow");

const bottomSpacerRef = useRef<HTMLDivElement>(null);
const messagesEndRef = useRef<HTMLDivElement>(null);
const scrollModeRef = useRef<ScrollMode>("stream-follow");
const anchoredUserMessageIdRef = useRef<string | null>(null);
const suppressScrollEventRef = useRef(false);
```

说明：

- `scrollMode` 用于驱动 effect 生命周期，让 `stream-follow` 和 `send-anchor` 真正分离。
- `scrollModeRef` 用于在 rAF 回调里读取最新模式，避免闭包拿到旧值。

### 3.4 底部结构

```tsx
<div
  ref={bottomSpacerRef}
  style={{ minHeight: bottomPadding, flexShrink: 0 }}
  aria-hidden
/>
<div
  ref={messagesEndRef}
  style={{ height: 0, flexShrink: 0 }}
  aria-hidden
/>
```

### 3.5 滚动状态机

#### `session-settle`

- 仅用于 session 切换后的历史消息定位。
- 保持现有 settle-to-bottom 行为。

#### `send-anchor`

- 用户发送消息后进入该状态。
- 将目标用户消息锚定到 `topInset` 位置。
- 在该状态下，禁止 `endSentinel` 的 near-bottom follow 抢回滚动。

#### `stream-follow`

- 仅当用户处于底部附近时启用。
- AI 流式增长时继续滚到底部。

#### `free-browse`

- 用户主动滚动后进入该状态。
- 不再自动滚动。

### 3.6 发送后进入 `send-anchor`

当 `messages.length` 增加时，检测是否为“用户刚发送”：

```tsx
if (lastMsg.role === "user") {
  anchoredUserMessageIdRef.current = lastMsg.id;
  scrollModeRef.current = "send-anchor";
}

if (
  lastMsg.role === "assistant" &&
  secondToLast?.role === "user"
) {
  anchoredUserMessageIdRef.current = secondToLast.id;
  scrollModeRef.current = "send-anchor";
  setScrollMode("send-anchor");
}
```

这里兼容两种实际路径：

- “用户消息 + 空 assistant 占位”在同一批渲染中到达。
- assistant 的首个正文 chunk 很快到达，导致最后一条 assistant 在首拍里已经带有内容。

实现上，这段判定应放在 `useLayoutEffect` 中，而不是普通 `useEffect`：

- `send-anchor` 必须在流式跟随的被动 effect 之前生效。
- 否则会出现“第一拍已经识别要锚定，但底部跟随还是先启动一次”的竞争。

### 3.7 `send-anchor` 的核心计算

在 `send-anchor` 状态下，每次消息更新都重新计算：

1. 锚定目标用户消息的位置。
2. 当前列表的真实可滚动上限是否足以把该消息推到目标位置。
3. 还需要多少 `bottomPadding` 才能让该消息稳定停在目标位置。

计算方式分成两部分：

```tsx
const topInset = parseFloat(getComputedStyle(container).paddingTop) || 0;
const targetHeight = target.offsetHeight;
const realBelowHeight = bottomSpacerRef.current.offsetTop - (target.offsetTop + targetHeight);
const legacyBottomPadding = Math.max(
  0,
  container.clientHeight - topInset - targetHeight - realBelowHeight
);

const targetTopWithinScroll =
  container.scrollTop + (targetRect.top - containerRect.top);
const desiredScrollTop = Math.max(0, targetTopWithinScroll - topInset);
const baseScrollHeight = container.scrollHeight - bottomPadding;
const maxBaseScrollTop = Math.max(0, baseScrollHeight - container.clientHeight);
const requiredBottomPadding = Math.max(0, desiredScrollTop - maxBaseScrollTop);

const nextBottomPadding = Math.max(legacyBottomPadding, requiredBottomPadding);
```

然后再滚动到：

```tsx
container.scrollTo({
  top: desiredScrollTop,
  behavior: "auto",
});
```

注意：

- 这里不再使用 `target.scrollIntoView({ block: "start" })`。
- 改用显式 `scrollTop` 计算，便于精确对齐“自然顶部留白”。
- 除了旧的几何估算，还会额外检查“当前最大可滚动距离是否足够”，避免真实浏览器里因为布局坐标系差异导致 padding 算少。
- `send-anchor` 使用 `behavior: "auto"`，避免平滑滚动触发连续 `scroll` 事件后过早退出锚定。

### 3.8 为什么不在首个 content chunk 到达时立刻清掉 padding

旧方案的问题就在这里。

如果 AI 一开始输出正文就立刻清掉 `bottomPadding`，而 near-bottom follow 仍处于启用状态，那么视口会重新被拉到底部。

当前版本里：

- `send-anchor` 状态期间，不让底部跟随逻辑介入。
- `bottomPadding` 采用“只增不减”的稳定策略。
- 一旦本轮回复算出需要的占位，就先保持住，避免短回复或布局抖动把用户消息再次拉回底部。

这样短回复不会回弹，真实页面里的几何波动也不会把锚定冲掉。

### 3.9 用户主动滚动时退出锚定

当前实现里，`onScroll` 不再直接结束 `send-anchor`：

- `scroll` 事件里混有程序滚动、浏览器补发事件和布局回流，直接拿它判断“用户主动打断”不可靠。
- 因此当前版本优先保证 anchor 稳定，不在这里清理 `bottomPadding`。
- 若后续需要支持“用户主动拖动就退出锚定”，建议单独通过 wheel / touch / pointer 等显式输入事件实现。

```tsx
if (scrollModeRef.current === "send-anchor") {
  return;
}
```

### 3.10 near-bottom follow 的新边界

流式期间的 rAF 跟随逻辑只在以下条件下运行：

```tsx
if (
  scrollModeRef.current === "stream-follow" &&
  anchoredUserMessageIdRef.current === null &&
  isNearBottomRef.current
) {
  messagesEndRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
}
```

也就是说：

- `send-anchor` 状态下，不允许 follow 抢回视口。
- 只要当前锚点还存在，也不允许 follow 介入。
- `free-browse` 状态下，也不允许 follow 干扰用户。

---

## 四、对现有逻辑的改动

### 4.1 会话切换

保留原来的 settle-to-bottom 行为，但新增重置：

```tsx
setBottomPadding(0);
anchoredUserMessageIdRef.current = null;
scrollModeRef.current = "session-settle";
```

### 4.2 新消息到来

不再简单区分“user / assistant 后不处理”。

而是：

- 检测是否进入 `send-anchor`
- 记录目标用户消息 id
- 后续由专门的 `send-anchor` effect 完成 spacer 和 scrollTop 计算

### 4.3 流式跟随

从“只要 `isStreaming && nearBottom` 就滚到底”改为：

- `scrollMode === "stream-follow"`
- 且 `isNearBottom === true`

### 4.4 清除占位

不再使用“第一个 content chunk 到达就清零”的策略。

改为：

- `send-anchor` 状态下先稳定保留本轮所需占位。
- 切 session 或下一轮发送时再重算。

---

## 五、边界情况

| 场景 | 处理 |
|------|------|
| 消息很少，列表原本不够高 | `bottomSpacer` 临时撑高，保证锚定成功 |
| AI 回复很短 | 保持锚定，不回弹到底部 |
| AI 回复很长 | 仍保持 anchor 稳定，避免内容增长过程把消息拉回底部 |
| 用户主动滚动 | 当前版本不通过普通 `scroll` 直接退出；若需要更强交互控制，后续再补显式输入事件 |
| 用户滚回底部附近 | 当前版本优先保持本轮 anchor 稳定，下一轮消息再重新计算 |
| 会话切换 | 清理锚定状态，使用原有 settle-to-bottom |
| 连续快速发送 | 每次发送覆盖上一次 anchor target，重新计算 spacer |

---

## 六、涉及文件

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `frontend/src/components/chat/chat-panel.tsx` | 修改 | 新增滚动状态机、拆分 `bottomSpacer` / `endSentinel`、改写发送后锚定与流式跟随逻辑 |
| `frontend/src/components/chat/message-item.tsx` | 小改 | 补充稳定的消息行标识，便于精确定位锚定目标 |
| `frontend/tests/components/chat/chat-panel.scroll-anchor.test.tsx` | 新增 | 覆盖“发送后顶部锚定”和“正文开始后不回弹到底部” |

---

## 七、验收标准

1. 用户发送消息后，用户消息停在消息区顶部自然留白处，不贴边。
2. AI spinner / 工具状态出现在该用户消息正下方。
3. AI 正文开始后，短回复不会把视口拉回到底部。
4. 普通浏览器 `scroll` 事件不会把本轮 anchor 误清掉。
5. 切换 session 或下一轮发送时，锚定状态会被正确重置。
