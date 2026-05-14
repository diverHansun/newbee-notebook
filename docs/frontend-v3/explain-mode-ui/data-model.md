# data-model.md — explain-mode-ui

## 一、范围说明

本模块仅在前端运行时维护少量状态，不涉及后端持久化或 DB schema 变更。本文件描述的"数据模型"是**运行时 TypeScript 类型与状态机**，而非数据库实体。

---

## 二、核心实体

### 1. ExplainCardState（扩展既有）

位置：`frontend/src/stores/chat-store.ts`。

| 字段 | 类型 | 已有/新增 | 含义 |
|---|---|---|---|
| `visible` | `boolean` | 已有 | 卡片是否被请求展示（一次性触发的语义残留，主要由 explainCard 是否为 null 表达） |
| `mode` | `"explain" \| "conclude"` | 已有 | 当前模式 |
| `selectedText` | `string` | 已有 | 用户在 Reader 中选中的原文 |
| `content` | `string` | 已有 | typewriter 暴露给视图的可见内容（**注意：不等于后端累积 delta**） |
| `isStreaming` | `boolean` | 已有 | 是否正在接收 SSE |
| **`error`** | **`ExplainCardError \| null`** | **新增** | 错误结构；非 null 时 body 渲染独立错误块 |
| **`lastInteractionKey`** | **`string`** | **新增** | `${mode}::${selectedText}` 的哈希字符串，用于触发 body 的 React `key` 变更与 fade-in 重挂 |

### 2. ExplainCardError（新）

```ts
type ExplainCardError = {
  code: string;        // SSE error_code 或前端定义码（如 "E_STREAM" / "E_NETWORK"）
  message: string;     // 用户可见文案，已是翻译后的字符串
  retryable: boolean;  // 是否在错误块中展示"重试"按钮
};
```

**字段约定**：

- `code` 由后端传来时直接透传；前端兜底（网络异常）填 `"E_NETWORK"`。
- `message` 优先用后端文案，前端兜底走 i18n key `explainCard.error.generic`。
- `retryable` 默认 `true`；对 4xx 类不可重试错误（如鉴权失败）由错误码映射为 `false`。本批次仅实现默认 `true`，映射表留待后续批次扩展。

### 3. TypewriterBufferState（运行时，不入 store）

由 `useTypewriterBuffer` hook 内部维护，**不进入 Zustand store**——避免 typewriter tick 触发不必要的全局订阅广播。

```ts
type TypewriterBufferState = {
  rawAccumulated: string;       // 后端到达的全部 delta 拼接结果
  visibleCharCount: number;     // 当前已暴露给消费方的可见字符数
  rafHandle: number | null;     // 当前 requestAnimationFrame 句柄
  flushed: boolean;             // 是否已 flush（done / error 后置 true）
  lastTickMs: number;           // 上一次 tick 的时间戳，用于节流
};
```

**核心方法签名**：

```ts
type TypewriterBuffer = {
  push(delta: string): void;    // 累积后端 delta；自动启动 rAF tick
  flush(): void;                // 立即把所有剩余字符暴露完毕，停止 rAF
  reset(): void;                // 清空状态（新会话/模式切换时调用）
};
```

### 4. ChatStore Action 扩展

新增以下 actions（chat-store.ts）：

```ts
setExplainError(error: ExplainCardError | null): void;
clearExplainError(): void;                       // 等价于 setExplainError(null)
bumpExplainInteractionKey(): void;               // 用 mode+selectedText 生成新 lastInteractionKey
```

保留以下既有 actions（行为不变）：

- `setExplainCard(state | updater)`
- `appendExplainContent(delta)` — 仍由 typewriter buffer 调用，行为不变

---

## 三、状态转移

```
                ┌─── selectedText / mode 改变 ──┐
                ▼                                │
   [null]  ──setExplainCard──>  [streaming, content="", error=null]
                                       │
                          SSE content   │
                          ┌────────────▼────────────┐
                          │ [streaming, content=部分] │
                          └────┬────────────────┬───┘
                               │                │
                       SSE done│                │ SSE error / 网络异常
                  buffer.flush ▼                ▼ buffer.flush
                  [done, isStreaming=false,    [streaming|done, error={...}]
                   error=null]                       │
                       │                             │ 用户点"重试"
                       │ 用户选新文本/切换模式       │
                       │                             │
                       └──────► [streaming, ...] ◄───┘
                                  (lastInteractionKey 更新触发 fade-in)
```

### 关键不变量

1. `content` 单调增长直至 `done`，**不会被错误覆盖**。错误期间 `content` 保留最后一次 buffer 输出的状态，用户仍可读已生成部分。
2. `error !== null` 与 `isStreaming === true` 可以并存（中途出错但流未真正终止），优先级为：**error 渲染压过 loader**。
3. `lastInteractionKey` 仅在用户主动切换模式或选中新文本时变化；同一会话内的多次 token append 不会改变它（否则会反复 fade-in）。

---

## 四、可见内容 vs 原始累积

`appendExplainContent` 接收的是 **typewriter buffer 暴露出来的可见字符增量**，而不是 SSE 原始 delta。两者的关系：

```
SSE event.type === "content"
       │
       │ event.delta（可能 1 char，也可能 100 chars 一块）
       ▼
useTypewriterBuffer.push(delta)
       │
       │ 累积到 rawAccumulated
       ▼
rAF tick (16-32ms)
       │
       │ 根据 markdown-typewriter.buildMarkdownVisibleMap 计算下一个 visibleCharCount
       │ 切片得到 visibleSlice = sliceMarkdownByVisibleChars(rawAccumulated, visibleCharCount)
       ▼
chat-store.appendExplainContent(visibleSlice.delta)
       │
       ▼
explainCard.content (视图层订阅)
```

最终 `done` 触发 `flush()` 后：

```
chat-store.explainCard.content === rawAccumulated
```

即"最终一致"。在 streaming 中途，`content` 可能滞后 rawAccumulated 数十到数百字符，**这是预期行为**。

---

## 五、错误模型

| 来源 | error 字段构造 |
|---|---|
| SSE `event.type === "error"` | `{ code: event.error_code, message: event.message, retryable: true }` |
| `fetch` 抛错 / 网络中断且未收到 `done` | `{ code: "E_NETWORK", message: t("explainCard.error.generic"), retryable: true }` |
| Persisted reply fallback 命中 | **不设错误**，反而清空 error 并把 fallback content 注入 `explainCard.content`（保留既有 fallback 语义） |
| 接收到 SSE `error` 但已收过 `done` | **静默忽略**——`done` 视为终态权威 |

**错误清空时机**：

- 用户点击"重试"按钮 → `clearExplainError()` 后重发请求。
- 用户选中新文本触发新一轮 explain / conclude → `setExplainCard(...)` 整体重置时 `error: null`。
- 折叠 pill 不清错误（保留状态，重展开仍可见错误块）。

---

## 六、与既有数据模型的兼容性

- `ChatMessage`、`ToolStep`、`ChatSession` 等既有类型**完全不动**。
- explain / conclude 的请求仍按原路径走 `sendMessage(message, mode, ...)`，请求 payload 不变。
- 后端持久化的 assistant reply（用于 fallback）格式不变。

---

## 七、未来演化预留

以下字段在本批次**不引入**，但未来"对话记录式可回溯消息条"批次预计会扩展：

- `explainHistory: ExplainCardEntry[]` —— 取代单 `explainCard` 对象，承载历史条目
- `sources: SourceCitation[]` —— 来自后端 `sources` 事件
- `phase: "reasoning" | "retrieving" | "synthesizing" | null` —— 阶段标签

文档此处显式提及，是为了让本批次的字段命名与未来扩展兼容（如不抢占 `explainHistory` / `sources` / `phase` 这三个名字）。
