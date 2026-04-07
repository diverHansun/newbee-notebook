# AI 消息 Spinner 动效优化设计

## 概述

本文档描述 AI 消息流式响应过程中三类状态指示器的视觉优化方案。核心目标：**去除廉价卡片感，提升动效质感，保持克制的设计调性。**

与已有文档的关系：

- `assistant-message-layout-plan.md` — 定义了去气泡、去头像的整体布局决策。
- `intermediate-content-plan.md` — 定义了中间态事件的数据流和后端协议。
- 本文档 — 在上述基础上，专注于 Thinking / Tool Steps / 中间态消息三者的动效与样式重构。

---

## 一、设计原则

1. **无容器**：移除所有 `border` + `border-radius` + `background` 卡片包裹，与去气泡的 assistant 消息保持一致。
2. **无进度条**：移除底部 shimmer 进度条（`thinking-indicator-progress` / `tool-steps-progress`），这是"廉价感"的主要来源。
3. **单行占位**：Thinking 和 Tool Steps 始终只占一行，在同一位置通过 crossfade 平滑更替。
4. **颜色克制**：沿用 `--bee-yellow` / `--bee-amber` 暖金色系，不引入新色。
5. **动静分离色彩**：运动中的元素保持高饱和度吸引注意，静止/完成的元素降低存在感。

---

## 二、状态流转

三个 phase 始终占据同一行位置，通过 crossfade 平滑切换：

```
Phase 1 (Thinking)      ◌ AI 正在思考...            ← Orbiting Dot
                              ↓ 第一个 tool call 到来，crossfade 0.2s
Phase 2 (Tool Steps)    ◎ 正在搜索知识库...         ← 旋转圆环，只显示最新一条
                              ↓ thinkingStage === "synthesizing"，crossfade 0.2s
Phase 3 (Synthesizing)  ◌ AI 正在思考...            ← 复用 Phase 1 的 Orbiting Dot 和文案
                              ↓ content 到达
Phase 4                 (指示器消失，显示正式回复)
```

中间态消息（`intermediateContent`）独立于上述 phase，在有中间推理内容时单独渲染在指示器上方。

---

## 三、色彩策略 — 动静分离

核心思路：**运动中的元素保持高饱和度吸引注意，静止/完成的元素降低存在感。** 色彩强度的变化本身传达状态信息（活跃 vs 完成），而非纯装饰。

| 元素 | 状态 | 色彩处理 |
|------|------|---------|
| Orbiting Dot（3px） | 动态 | `--bee-amber` 全饱和，面积小 + 运动中，高饱和合理 |
| 旋转圆环（14px） | 动态 | `--bee-yellow → --bee-amber` 渐变，保持全饱和度 |
| Done 打钩 | 静态 | 背景 `--bee-amber / 0.1`，描边 `--bee-amber / 0.5`，明显退后 |
| Error 叉号 | 静态 | 保持现有红色方案不变 |
| 状态文字 | 静态 | `--muted-foreground`，不变 |
| 中间态消息 | 过渡态 | `--muted-foreground` + 斜体，14px |

---

## 四、Thinking Indicator — Orbiting Dot

### 4.1 视觉

```
◌  AI 正在思考...
```

- **无容器**：不渲染任何边框、背景、圆角。
- **圆点**：3px 实心圆，颜色 `hsl(var(--bee-amber))`（动态元素，保持全饱和度）。
- **文字**：12px，`hsl(var(--muted-foreground))`，静态不动。
- **整体布局**：`display: flex; align-items: center; gap: 8px;`，单行。

### 4.2 动效 — 椭圆轨道运动

圆点沿一个 16×16px 区域内的椭圆轨道缓慢运动，轨道本身不可见。

**实现方式**：通过 `translateX` 和 `translateY` 的不同周期 keyframe 组合，模拟椭圆路径：

```css
@keyframes orbit-x {
  0%, 100% { transform: translateX(0); }
  50% { transform: translateX(6px); }
}

@keyframes orbit-y {
  0%, 100% { transform: translateY(0); }
  25% { transform: translateY(-4px); }
  75% { transform: translateY(4px); }
}
```

- **周期**：X 轴 2s，Y 轴 2.8s（不同周期产生利萨如图形般的有机运动）。
- **缓动**：`ease-in-out`，让运动有自然的加速减速。
- **圆点元素**：同时应用两个动画 `animation: orbit-x 2s ease-in-out infinite, orbit-y 2.8s ease-in-out infinite;`

### 4.3 从当前实现的变更

| 移除 | 新增 |
|------|------|
| `.thinking-indicator` 的 border / border-radius / background / padding | 无容器的 flex 单行布局 |
| `.thinking-indicator-ring`（conic-gradient 旋转环） | orbiting dot（3px 圆点 + 椭圆轨道动画） |
| `.thinking-indicator-progress` / `-progress-bar`（底部 shimmer） | 无 |

---

## 五、Tool Steps Indicator — 单行最新工具

### 5.1 视觉

```
◎ 正在搜索知识库...        ← running 状态
✓ 网络搜索                  ← done 状态（短暂可见）
```

- **无容器**：不渲染任何边框、背景。
- **始终只显示最新一条** tool step，不再渲染完整列表。
- **布局**：`display: flex; align-items: center; gap: 8px;`，单行，与 Thinking Indicator 位于同一位置。

### 5.2 状态图标（动静分离色彩策略）

**running 状态**（动态 — 保持高饱和度）：
- 14px conic-gradient 旋转圆环（`bee-yellow → bee-amber → bee-yellow`），保持全饱和度
- 内部挖空（`::after` inset 2px），背景色从 `hsl(var(--muted) / 0.5)`（旧卡片背景）改为 `hsl(var(--background))`（页面背景）
- 动画 `thinking-spin 1s linear infinite`

**done 状态**（静态 — 降低存在感）：
- 14px 圆形，背景从 `hsl(var(--bee-amber) / 0.2)` 降至 `hsl(var(--bee-amber) / 0.1)`
- 内部 `::after` 绘制打钩，描边从 `hsl(var(--bee-amber))` 降至 `hsl(var(--bee-amber) / 0.5)`
- 文字透明度保持 `hsl(var(--muted-foreground) / 0.6)`

**error 状态**（保留现有设计）：
- 14px 圆形，`hsl(0 70% 50% / 0.2)` 背景
- 内部 `::before` + `::after` 绘制叉号
- 文字变红 `hsl(0 70% 50% / 0.8)`

### 5.3 Step 切换过渡

当新的 tool step 到来时：
- 当前行 fade-out（opacity 1→0，0.15s ease-out）
- 新行 fade-in（opacity 0→1，0.15s ease-in，延迟 0.05s）
- 实现：可通过 `key` 变化触发 CSS animation，或用 React 的 `key` prop 强制重新挂载 + 入场动画。

### 5.4 从当前实现的变更

| 移除 | 新增 |
|------|------|
| `.tool-steps-indicator` 的 border / border-radius / background / padding | 无容器的 flex 单行布局 |
| `.tool-steps-list` 多行列表渲染 | 只渲染 `toolSteps` 数组中最后一个元素 |
| `.tool-steps-progress` / `-progress-bar`（底部 shimmer） | 无 |
| `isSynthesizing` 时在列表末尾追加"正在生成"行 | 切回 ThinkingIndicator（由 message-item.tsx 控制） |

---

## 六、中间态消息 — 斜体文字

### 6.1 视觉

```
AI 正在分析你的问题，让我先看看相关的文档内容...    ← 斜体，muted 色，14px
```

### 6.2 样式变更

- **移除** `.assistant-intermediate-text` 的 `border-left: 2px solid hsl(var(--bee-yellow) / 0.35)` 和 `padding-left: 14px`。
- **新增** `font-style: italic`。
- **保留** `font-size: 14px`。
- **保留** `color: hsl(var(--muted-foreground))`、`line-height: 1.65`、`white-space: pre-wrap`。
- **保留** 入场动画 `intermediate-slide-up-in 0.24s ease-out` 和出场动画 `intermediate-fade-up-out 0.22s ease-out forwards`。

---

## 七、message-item.tsx 逻辑变更

### 7.1 ToolStepsIndicator 只渲染最新 step

```tsx
// 当前：渲染全部 steps
steps.map((step) => <div>...</div>)

// 改为：只取最后一个
const latestStep = steps[steps.length - 1];
// 渲染单个 step
```

### 7.2 synthesizing 时切回 ThinkingIndicator

当前逻辑中 `showThinkingIndicator` 的判断条件为 `!hasToolSteps`，但当 `toolSteps.length > 0` 且 `thinkingStage === "synthesizing"` 时，应切回 thinking：

```tsx
const isSynthesizing = !isUser
  && message.status === "streaming"
  && !message.content
  && message.thinkingStage === "synthesizing";

const showThinkingIndicator =
  !isUser && message.status === "streaming" && !message.content
  && (!hasToolSteps || isSynthesizing);

// Tool steps 只在有 steps 且非 synthesizing 时显示
const showToolSteps = hasToolSteps && !isSynthesizing;
```

---

## 八、涉及文件

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `frontend/src/styles/thinking-indicator.css` | 重写 | 移除卡片/shimmer；重写为无容器单行布局；中间态去竖线加斜体 |
| `frontend/src/styles/animations.css` | 修改 | 新增 `orbit-x` / `orbit-y` keyframe；移除 `thinking-shimmer` |
| `frontend/src/components/chat/message-item.tsx` | 修改 | ToolStepsIndicator 只渲染最新 step；synthesizing 切回 ThinkingIndicator |
