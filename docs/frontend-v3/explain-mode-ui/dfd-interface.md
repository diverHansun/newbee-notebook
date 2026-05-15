# dfd-interface.md — explain-mode-ui

## 撰写前置确认

- 模块职责边界已在 `goals-duty.md` 中确认。
- 模块内部结构已在 `architecture.md` 中描述：`ExplainCard` 单文件宿主 + `useTypewriterBuffer` hook。
- 核心数据类型 `ExplainCardState` / `ExplainCardError` / `TypewriterBufferState` 已在 `data-model.md` 中定义。

---

## 一、Context & Scope（上下文与范围）

本模块位于**前端渲染层与状态层之间**，上游接收来自 `useChatSession` 的 SSE 事件流，下游驱动 `ExplainCard` 视图。

### 外部交互对象

| 方向 | 对端 | 关系 |
|---|---|---|
| 上游输入 | `SelectionMenu`（不动） | 用户操作触发点 |
| 上游输入 | 后端 `POST /notebooks/{id}/chat/stream` | SSE 流式事件源 |
| 内部协调 | `useChatSession.ts` 的 explain 分支 | 事件消费 + 重发 + fallback |
| 状态枢纽 | `chat-store.explainCard` | 单向数据流的中心 |
| 下游消费 | `ExplainCard` 单文件宿主 | 接收 `explainCard` 与 `retryExplainCard`，渲染本地 UI 分支 |
| 平级依赖 | `markdown-typewriter` util | 可见字符切片计算 |
| 平级依赖 | `MarkdownViewer` 组件 | 内容最终渲染 |

### 本文档讨论范围

仅描述**事件流入 → buffer 节流 → store 更新 → 视图渲染**这条主线，以及"模式切换 / 错误 / 重试 / 折叠"等控制流。

**不在范围内**：

- 后端 SSE 的具体协议（已在 `docs/backend-v2/.../engine/07-explain-conclude-retrieval-policy.md` 描述）
- `MarkdownViewer` 的内部渲染管线
- `SelectionMenu` 的选中文本提取逻辑
- `useChatSession` 的 chat / ask 分支

---

## 二、Data Flow Description（数据流描述）

### 流 1：正常生成流程

```
[1] 用户在 Reader 中选中文本
     │
     ▼
[2] SelectionMenu 点击"解释"或"总结"
     │ 输出: { documentId, selectedText, mode }
     ▼
[3] useChatSession.sendMessage(message="", mode, context={selected_text, document_id})
     │
     ▼
[4] chat-store.setExplainCard({
       visible: true,
       mode,
       selectedText,
       content: "",
       isStreaming: true,
       error: null,
       lastInteractionKey: hash(mode, selectedText),
     })
     │
     ▼
[5] useTypewriterBuffer.reset()
     │
     ▼
[6] fetch SSE → 后端 retrieval iterations → synthesis
     │
     ▼
[7] SSE event 流：
     ┌─ event.type === "start"          → 记录 message_id（不进 store）
     ├─ event.type === "phase"          → 忽略（Non-Duty #6）
     ├─ event.type === "content"        → useTypewriterBuffer.push(event.delta)
     │                                    │
     │                                    ▼  rAF tick (16-32ms)
     │                                    │
     │                                    ▼
     │                                  appendExplainContent(visibleSlice)
     │
     ├─ event.type === "sources"        → 忽略（Non-Duty #1）
     ├─ event.type === "warning"        → 忽略（Non-Duty #6）
     ├─ event.type === "error"          → useTypewriterBuffer.flush();
     │                                    setExplainError({code, message, retryable: true})
     │
     └─ event.type === "done"           → useTypewriterBuffer.flush();
                                          setExplainCard(prev => ({...prev, isStreaming: false}))
     │
     ▼
[8] View 层订阅 explainCard，按状态分支渲染
```

### 流 2：模式切换流程

```
[1] 卡片已展示 explain 结果，用户选新文本点"总结"
     │
     ▼
[2] useChatSession.sendMessage(message="", mode="conclude", ...)
     │
     ▼
[3] setExplainCard({
       ...overwrite,
       content: "",
       error: null,
       lastInteractionKey: hash("conclude", newSelectedText)  ← 与上次不同
     })
     │
     ▼
[4] ExplainCard body 容器的 React key 变化 → 卸载旧 body → 挂载新 body
     │
     ▼
[5] CSS @keyframes fade-in 自动播放（150ms opacity 0→1）
     │
     ▼
[6] 后续与"流 1"的 [5] 起一致
```

### 流 3：错误与重试

```
[1] 流 1 进行中收到 SSE event.type === "error"
     │
     ▼
[2] flush buffer + setExplainError({code, message, retryable: true})
     │
     ▼
[3] ExplainCard 检测 error !== null → 渲染本地 error block
     │ error block 接收来自父级的 retry 回调
     ▼
[4] 用户点击"重试"按钮
     │
     ▼
[5] retry 回调 → clearExplainError() → 重新进入"流 1"的 [3]
     │ 使用原 message / mode / context 重发
     │ lastInteractionKey 保持不变 → 不触发 fade-in
     ▼
[6] 若再次失败 → 回到 [2]
```

### 流 4：网络中断 + 持久化 fallback

```
[1] 流 1 进行中 fetch 抛错（如 EventSource 中断），SSE 未收 done
     │
     ▼
[2] onError 回调判断：streamReceivedDone === false && streamReceivedErrorEvent === false
     │
     ▼
[3] 触发 findRecentPersistedAssistantReply 查询（既有逻辑）
     │
     ├── 命中：setExplainCard({content: reply.content, isStreaming: false, error: null})
     │
     └── 未命中：
          ├── chatOnce 兜底成功 → 同上
          └── 兜底失败 → setExplainError({code: "E_NETWORK", message: t(error.generic)})
```

### 流 5：折叠 / 展开

```
用户点击折叠按钮 → setCollapsed(true)
       │
       ▼
ExplainCard 渲染 pill（绝对定位于 #main-panel-section 右上角）
       │ store.explainCard 状态保持不变
       ▼
用户点击 pill → setCollapsed(false)
       │
       ▼
ExplainCard 渲染 aside（绝对定位）
       │ body 直接消费当前 store 状态，无 fade-in（lastInteractionKey 未变）
```

### 流 6：拖拽 / 缩放

```
用户在 titlebar 按下 → useDraggable.onPointerDown
       │
       ▼
position state 改变 → 卡片 transform: translate(x, y)
       │
       ▼
（不持久化；折叠/重展开重置为 {0, 0}）

用户在右下角拖拽 → useResizable.onResizePointerDown
       │
       ▼
size state 改变 → 卡片 width / height
       │
       ▼
（不持久化；折叠/重展开重置为 DEFAULT）
```

---

## 三、Interface Definition（接口定义）

### 1. useTypewriterBuffer

```ts
function useTypewriterBuffer(opts: {
  onDelta: (visibleDelta: string) => void;
  baseCharsPerSecond?: number;
  drainCharsPerSecond?: number;
}): {
  push: (delta: string) => void;
  flush: () => void;
  reset: () => void;
};
```

- 语义：消费方调用 `push(delta)` 累积；hook 内启动 rAF；按字符速率推进可见字符；通过 `onDelta(visibleDelta)` 把新增可见内容回调给消费方。
- 同步 vs 异步：`push` 同步；`onDelta` 异步在 rAF 中（`flush` 除外）。
- 终止：`flush()` 立即一次性 tick 到末尾；`reset()` 清空所有状态、停止 rAF。
- **复用 `markdown-typewriter.buildMarkdownVisibleMap` / `sliceMarkdownByVisibleChars`**：不重写可见字符计算逻辑。

### 2. chat-store.explainCard actions（扩展）

```ts
setExplainError(error: ExplainCardError | null): void;
clearExplainError(): void;
buildExplainInteractionKey(mode, selectedText): string;
```

- 行为均为同步 setState；订阅方通过 `useChatStore` selector 接收。

### 3. useChatSession.sendMessage（签名不变）

```ts
sendMessage(
  message: string,
  mode: "agent" | "ask" | "explain" | "conclude",
  context: ChatContext | null,
  sourceDocumentIds?: string[] | null,
  imageIds?: string[]
): Promise<void>;
```

本批次只改 explain / conclude 分支的**实现**，不改签名。

### 4. ExplainCard retry 接口

```ts
type ExplainCardProps = {
  card: ExplainCardState | null;
  onRetry?: () => void;
};
```

- onRetry 来自 `useChatSession.retryExplainCard`，由 `NotebookWorkspace` 透传给 `ExplainCard`。

### 5. ExplainCard 本地渲染分支

`ExplainCard` 内部根据 `(content, isStreaming, error)` 渲染 error / loader / empty / markdown content。分支不拆文件，因为它们没有复用方，生命周期也完全跟宿主一致。

---

## 四、Data Ownership & Responsibility（数据归属与责任）

| 数据 | 创建方 | 更新方 | 销毁方 | 责任 |
|---|---|---|---|---|
| `explainCard` 对象 | `useChatSession` (首次 setExplainCard) | `useChatSession` / `useTypewriterBuffer` | 不主动销毁，新会话覆盖 | useChatSession 维护其生命周期 |
| `explainCard.content` | `useTypewriterBuffer` 通过 `appendExplainContent` | 同上 | flush 后稳定 | typewriter buffer 是唯一写入者 |
| `explainCard.error` | `useChatSession` SSE error / 网络异常 | `clearExplainError`（用户重试） | 重试或新会话清空 | useChatSession 是唯一写入者 |
| `explainCard.lastInteractionKey` | `useChatSession` 在 mode / selectedText 变化时 | 新 explain / conclude 请求覆盖 | 跟随 explainCard 整体销毁 | useChatSession 是唯一写入者 |
| typewriter buffer 内部状态 | hook 本身 | hook push / tick / flush | hook reset / unmount | hook 完全自治，不暴露状态给外部 |
| pill / 卡片的 collapsed 状态 | `ExplainCard` 宿主组件 | 用户操作 | 组件卸载 | 局部 UI 状态，不入 store |
| pill / 卡片的 position / size | `useDraggable` / `useResizable` | 用户拖拽 | 组件卸载 / 重置 | 局部 UI 状态，不入 store（Non-Duty #4） |

### 关键责任边界

1. **useChatSession 拥有 explainCard 的所有"业务字段"写权限**（mode / selectedText / error / lastInteractionKey）；视图层只读。
2. **useTypewriterBuffer 拥有 content 字段的写权限**（通过 `appendExplainContent`）；buffer 是唯一暴露原始 delta 转可见字符的层。
3. **视图组件不写 store**——仅 ExplainCard 容器组件的局部 `collapsed` / `position` / `size` 是本地 state。
4. **错误不污染内容**：`error` 与 `content` 两个字段相互独立，永远不能在 content 里出现错误码字符串。

---

## 五、关键数据流的可验证性

每条数据流都对应可断言的事实：

| 数据流 | 可验证事实 |
|---|---|
| 流 1 | streaming 期间 content 单调增长；done 时 content === sum(deltas) |
| 流 1 typewriter | content 增长速率 ≤ 后端 delta 速率（节流生效） |
| 流 2 模式切换 | mode 变化时 ExplainCard body 容器卸载重挂（key 不同） |
| 流 3 错误 | error !== null 时 error block 出现，content 保持不变 |
| 流 4 fallback | 网络异常 + 持久化命中时 explainCard.content 被注入，error === null |
| 流 5 折叠 | setCollapsed(true) 后 explainCard 状态不变 |
| 流 6 拖拽 | 折叠重展开后 position === {0, 0} |

这些事实对应 `test.md` 中的 Critical Scenarios 与组件测试断言。
