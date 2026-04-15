# AI 消息呈现方案

## 概述

本文档专门讨论 AI 消息在会话列表中的视觉呈现，不重复描述中间态事件的数据流和后端协议。目标是把 AI 消息渲染成更接近 ChatGPT Web 的形式：**去掉 AI 头像、去掉 AI 气泡，让 AI 内容直接成为会话正文的一部分。**

与 `intermediate-content-plan.md` 的关系：

- `intermediate-content-plan.md` 负责数据流、事件和状态更新。
- 本文档负责视觉结构、动画和消息层级。

---

## 一、设计目标

1. AI 最终消息不使用卡片气泡，而是直接渲染在正文轨道中。
2. AI 中间态消息和最终消息共享同一条 assistant 内容轨道，降低切换割裂感。
3. 用户消息保留右侧气泡，但用户头像也一并去掉，让会话更干净。
4. 中间态文本在下一段中间态到来前持续保留，帮助用户保留上下文。
5. 当下一段中间态开始时，旧中间态渐隐上移，新中间态从底部向上进入。
6. 用户取消流时，不保留中间态文本，直接清理瞬态区域。
7. 中间态文本不做打字机效果；最终 assistant 正文保留自然流式输出效果。

当前默认目标 provider 为 `glm-5`，因此视觉体验按“存在中间态文本”进行优先设计；`qwen3.5-plus` 仍需保留无中间态回退展示。

---

## 二、核心判断

### 2.1 中间态和最终消息要不要用同一种样式？

建议：**同一视觉家族，不同视觉权重。**

也就是说：

- 它们都位于 assistant 正文轨道内。
- 都不使用气泡。
- 都使用相同的内容宽度约束和左对齐方式。

但不建议做成完全一样：

- 最终消息：正常 Markdown 正文样式，颜色为标准前景色。
- 中间态消息：纯文本、弱化色、带进入/退出动画，但不做字符级打字机效果。

原因：

1. 如果完全不同，切换时会像换了一个组件，视觉跳变更明显。
2. 如果完全一样，用户很难区分“暂时思路”与“最终答案”。

所以最合理的是：**布局统一，语义区分。**

### 2.2 去掉 AI 气泡和头像是否值得？

值得。

原因不是单纯“更像 ChatGPT”，而是它确实会降低这次中间态方案的布局复杂度：

1. 中间态和最终消息不再需要跨越两个不同卡片组件切换。
2. 中间态 entering/exiting 动画不再受气泡 padding、边框和阴影影响。
3. ToolStepsIndicator 和 ThinkingIndicator 可以自然地放在 assistant 文本区块下方，而不是塞进气泡外层。

---

## 三、推荐结构

### 3.1 会话项结构

```tsx
<MessageRow>
  {isUser ? <UserBubble /> : null}

  {!isUser ? (
    <AssistantLane>
      <AssistantIntermediateExiting />
      <AssistantIntermediateCurrent />
      <AssistantFinalContent />
      <ThinkingIndicator or ToolStepsIndicator />
      <Sources />
      <Confirmation />
    </AssistantLane>
  ) : null}
</MessageRow>
```

### 3.2 视觉行为

- 用户：右对齐气泡。
- assistant：左对齐正文轨道，无头像、无 bubble。
- sources 和 confirmation 继续附着在 assistant 轨道下方。

---

## 四、动画建议

### 4.1 需要两个中间态槽位

如果想实现“上一段渐隐，新一段从底部弹出”，就不能只存一个 `intermediateContent`。

建议增加：

```typescript
intermediateContent?: string;
exitingIntermediateContent?: string | null;
intermediateGeneration?: number;
```

### 4.2 动画时序

#### 场景 A：第一段中间态到来

1. `intermediateContent` 从空变为第一段文本。
2. 当前中间态块从底部向上进入。
3. 下方继续显示 ThinkingIndicator 或 ToolStepsIndicator。
4. 后续同一段中间态的 delta 直接更新当前文本，不附加打字机动画。

#### 场景 B：下一轮中间态到来

1. 旧 `intermediateContent` 复制到 `exitingIntermediateContent`。
2. `intermediateContent` 清空，等待新一轮 delta。
3. 新 delta 到来后写入 `intermediateContent`。
4. `exitingIntermediateContent` 做 fade-up-out。
5. 新 `intermediateContent` 做 slide-up-in。

#### 场景 C：最终消息到来

1. 当前 `intermediateContent` 复制到 `exitingIntermediateContent`。
2. 第一个 final content delta 写入 assistant 正文。
3. 旧中间态淡出，最终正文留在原位继续流式追加。
4. 最终正文不做上弹动画，只保留流式输出节奏。

#### 场景 D：取消

1. 清空 `intermediateContent`。
2. 清空 `exitingIntermediateContent`。
3. 停止显示 ThinkingIndicator / ToolStepsIndicator。

---

## 五、为什么这个方向比“继续保留 AI 气泡”更合适

1. 中间态和最终正文切换更自然，因为两者不再跨组件边界。
2. assistant 内容看起来更像一条连续思路，而不是一串卡片。
3. 进入和退出动画可以只围绕文本本身设计，不用处理 bubble 外框和 avatar 对齐。
4. 对长回答更友好，尤其是 Markdown 内容较多时，正文轨道比卡片更稳。

---

## 六、实施建议

1. 先在 `MessageItem` 中去掉 assistant avatar 和 assistant bubble。
2. 同时去掉 user avatar，只保留 user bubble。
3. 再补 `exitingIntermediateContent` 和两段动画。
4. 最终正文优先直接按 SSE delta 追加；如果需要更平滑，可增加极轻量帧级缓冲，但不要人为减慢输出速度。
5. 最后再细调 spacing、颜色和 indicator 位置。

---

## 七、待确认事项

1. assistant 轨道是否需要保留很轻的左侧视觉锚点，比如 1px 细线或段前间距，而不是完全裸文本。
2. 中间态文本颜色要弱化到什么程度，既要像“暂态”，又不能让用户看不清。
3. sources 和 confirmation 是继续跟在 assistant 正文后，还是在长文本场景下拆成独立区块。
4. 最终正文如果引入显示缓冲，刷新节奏上限要控制在多快。当前建议不要低于每帧一次的自然刷新体感。