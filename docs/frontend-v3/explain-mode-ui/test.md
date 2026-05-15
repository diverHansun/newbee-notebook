# test.md — explain-mode-ui

## Module Test Profile

- **模块原型**：服务编排模块（前端 hook 编排 SSE 事件 + buffer + store）+ 纯逻辑模块（typewriter buffer）混合
- **主要测试类型**：unit（buffer / store action）+ component（RTL 渲染断言）+ integration（hook 串联 SSE mock 与 store）
- **Mock 边界**：
  - SSE / fetch：完全 mock（用既有的 `mockStream` helper 或 MSW）
  - `markdown-typewriter` util：使用真实实现（已稳定，多场景共享）
  - `MarkdownViewer`：在组件测试中 mock 为简单 `<pre>{content}</pre>`，避免引入其内部 markdown 解析复杂度
  - `useDraggable` / `useResizable`：使用真实实现（既有逻辑，不在本批次重写）
  - Zustand `chat-store`：真实实例（in-test 重置）
- **测试归属目录**：
  - 单元：`frontend/tests/lib/utils/`、`frontend/tests/lib/hooks/`
  - 组件：`frontend/src/components/chat/__tests__/`（沿用既有 colocated 测试约定）
  - 集成：`frontend/tests/lib/hooks/useChatSession.explain-session.test.tsx`（已存在，扩展）

---

## Test Scope

### 覆盖

- `useTypewriterBuffer` 的累积、节流、flush、reset 行为及其与 `markdown-typewriter` 的集成。
- `useChatSession` explain / conclude 分支的 SSE 事件消费（content / done / error / 网络异常）。
- `chat-store.explainCard` 的状态字段扩展与新 actions / helper（`setExplainError` / `clearExplainError` / `buildExplainInteractionKey`）。
- `ExplainCard` 单文件宿主的状态分支渲染（empty / loading / streaming / done / error）。
- 模式切换的 `lastInteractionKey` 变化与 fade-in 触发。
- 错误状态下 content 保持不变的契约。
- pill 与卡片均挂载于 `#main-panel-section` 内部的回归断言。

### 不覆盖

- 后端 SSE 协议本身的正确性（由后端 batch-2 测试覆盖）。
- `markdown-typewriter` 的内部实现（已有 `markdown-typewriter.test.ts` 单测）。
- `MarkdownViewer` 的 markdown 渲染（既有测试覆盖）。
- `SelectionMenu` 的选中文本提取（Non-Duty #3，本批次不动）。
- 视觉回归（screenshot 对比留给手动 QA + Playwright e2e 流程，不在本模块单测中）。
- 拖拽 / 缩放的手势细节（沿用既有 `useDraggable` / `useResizable` 测试）。

---

## Critical Scenarios

### 1. typewriter buffer 节奏正确

**正常路径**

- `push("Hello, ")` + `push("世界")` 多次累积，rawAccumulated 正确拼接。
- 每个 rAF tick 暴露 ≤ 3 个可见字符；用 `vi.useFakeTimers()` 推进虚拟时间断言每帧 onTick 调用参数。
- 暴露的 visibleSlice 跨 markdown 标记字符（`**bold**`）时不破坏可见字符计数（依赖 `buildMarkdownVisibleMap`）。

**flush 路径**

- 中途 push 后立刻 flush，onTick 应被调用一次且参数为 rawAccumulated 的完整可见切片。
- flush 后 rAF 句柄被取消（断言 `cancelAnimationFrame` 被调用）。

**reset 路径**

- reset 后 rawAccumulated、visibleCharCount 归零；新 push 从零开始。

### 2. SSE 事件 → store 转换正确

**正常路径**

- mock SSE 发出 `start` → `content("Hel")` → `content("lo")` → `done`：
  - store.explainCard.content 最终 === "Hello"
  - store.explainCard.isStreaming === false
  - store.explainCard.error === null

**错误路径 A：SSE error 事件**

- mock SSE 发出 `content("Hel")` → `error({code:"E_X",message:"boom"})`：
  - store.explainCard.error === `{code:"E_X", message:"boom", retryable:true}`
  - store.explainCard.content === "Hel"（**不变**）
  - store.explainCard.isStreaming === false

**错误路径 B：网络中断 + fallback 命中**

- mock fetch 抛错；mock `findRecentPersistedAssistantReply` 返回 `{content:"backup"}`：
  - store.explainCard.content === "backup"
  - store.explainCard.error === null
  - store.explainCard.isStreaming === false

**错误路径 C：网络中断 + fallback 未命中 + chatOnce 失败**

- store.explainCard.error.code === "E_NETWORK"
- store.explainCard.isStreaming === false

**错误路径 D：done 之后再来 error 事件**

- 静默忽略；store.explainCard.error 保持 null。

### 3. 模式切换触发 fade-in

- 初始 sendMessage(mode="explain", selectedText="A") → store.explainCard.lastInteractionKey = K1
- 用户再触发 sendMessage(mode="conclude", selectedText="A") → lastInteractionKey = K2 ≠ K1
- 同一模式 + 同一文本再次触发不变更 key（断言 K === K1）

### 4. ExplainCard 状态分支渲染

| 状态 | 期望渲染 |
|---|---|
| `content="" && isStreaming=true && error=null` | loader 分支出现，`role="status"` |
| `content="" && isStreaming=false && error=null && explainCard=null` | empty 分支出现，含 i18n emptyTitle |
| `content="some text" && isStreaming=true && error=null` | `<MarkdownViewer />` 渲染 "some text"，loader 不出现 |
| `error !== null`（无论其他字段） | error block 出现，含 i18n error.retry 按钮；loader 不出现 |
| `content="partial" && error !== null` | 错误块 + content 同时可见 |

### 5. 重试流程

- 触发 error 状态 → 点击 "重试" 按钮 → 断言：
  - `clearExplainError` 被调用
  - 上次请求的 `message` / `mode` / `context` 被重发（mock useChatSession.sendMessage 检查参数）
  - lastInteractionKey 不变（重试不算模式切换）

### 6. 折叠 / 展开行为

- 卡片展开态点击折叠 → 渲染 pill；store 状态不变。
- 折叠态点击 pill → 渲染卡片；body 不触发 fade-in。
- 折叠态下 SSE content 事件到达：store.content 仍在变；重展开后看到完整内容。

### 7. 错误不污染 content

- 不论触发什么 SSE error / 网络异常，`content` 字段中**不出现** `[E_*]` 字符串前缀。
- 错误信息只在 `error.message` 字段，由 `ExplainCard` 的 error block 独立渲染。

### 8. 定位重构回归

- 渲染 `<NotebookWorkspace />`（mock 子组件减少噪音），断言：
  - pill 的 DOM parent 是 `#main-panel-section`
  - 展开的卡片 DOM parent 也是 `#main-panel-section`
  - 没有创建 portal 到 `document.body`

---

## Integration Points

### 1. 与 `useChatSession` 集成

- 测试入口：`useChatSession.explain-session.test.tsx`（已存在，扩展）。
- mock SSE 完成完整事件序列（start → content × N → done）；断言 store 终态正确、typewriter buffer 已 flush。
- 失败模式：mock SSE 抛错；断言 fallback 链路与 error 字段写入。

### 2. 与 `markdown-typewriter` 集成

- 用 `*粗体*` / `[link](url)` / 代码块 / 中文混合的累积字符串测试 `useTypewriterBuffer` 暴露的 visibleSlice。
- 断言 visibleSlice 永远是 `markdown-typewriter.sliceMarkdownByVisibleChars` 的合法输出（不在 markdown 标记中间断开）。

### 3. 与 `chat-store` 集成

- 新增 actions / helper 单测：`setExplainError`、`clearExplainError`、`buildExplainInteractionKey`。
- 断言 `buildExplainInteractionKey` 在相同 mode/selectedText 下幂等。

### 4. 与 `notebook-workspace` 集成

- `ExplainCard` 从 `mainOverlay` 移到 `mainInner` 后，断言 `#main-panel-section` 的 `position: relative` 正确设置。
- 断言 z-index 层级：pill < 卡片 < Main 面板其他浮层（如代码块复制按钮，若有）。

---

## Verification Strategy

### 1. 执行环境

- 运行：`pnpm --filter frontend test`
- 框架：`vitest` + `@testing-library/react` + `@testing-library/user-event`
- 时间控制：`vi.useFakeTimers()` 推进 rAF / setTimeout，避免真实 16ms 等待
- DOM：`jsdom`

### 2. Mock 策略

| 依赖 | mock 方式 |
|---|---|
| SSE stream | 复用 `tests/lib/hooks/useChatSession.*.test.tsx` 中现有 `mockStream` helper |
| `fetch` | MSW 或 vi.fn |
| `findRecentPersistedAssistantReply` | `vi.spyOn` |
| `chatOnce` | `vi.spyOn` |
| `requestAnimationFrame` | vitest 默认 jsdom polyfill；用 fake timers 控制 |
| `MarkdownViewer` | 在组件测试中 `vi.mock(...)` 为简化版 |

### 3. 测试分层

| 层 | 文件 | 数量级 |
|---|---|---|
| 纯单元 | `useTypewriterBuffer.test.ts` | 8-12 例 |
| 纯单元 | `chat-store.test.ts`（新 actions） | 4-6 例 |
| 组件集成 | `explain-card.test.tsx` | 6-10 例（状态分支、folding、retry） |
| Hook 集成 | `useChatSession.explain-session.test.tsx`（扩展） | 新增 6-8 例 |

### 4. 视觉验证（不在单测）

- 手动 QA 在 `pnpm dev` 起服务下执行 `quickstart.md` 中的浮卡流程。
- Playwright e2e（若已有 setup）扩展 `explain-flow.spec.ts`：覆盖 UC-1 / UC-2 / UC-4 主路径。
- 视觉回归（screenshot）暂不自动化，留作手动 QA 比较 before/after。

### 5. CI 门槛

- 单元 + 组件测试必须通过（`pnpm --filter frontend test` 退出 0）。
- 类型检查：`pnpm --filter frontend typecheck` 通过。
- Lint：`pnpm --filter frontend lint` 无新增 warning。
- a11y：本批次不强制 axe 集成，但实施 PR 描述中需附 axe 手动扫描截图（卡片各态各一张）。

---

## 自检清单

- [ ] Module Test Profile 已声明（混合原型）
- [ ] Test Scope 覆盖 8 个 Duty 中的可测试部分（Duty 1 视觉重构主要靠手动 QA + a11y 扫描）
- [ ] Critical Scenarios 含正常路径 + 至少 4 类异常路径
- [ ] Integration Points 含 4 个外部协作对象
- [ ] Verification Strategy 含 mock 边界、时间控制、测试分层
- [ ] 测试归属目录与项目既有约定一致
- [ ] 未与具体实现细节绑定（不断言私有变量、不依赖未公开的 hook 内部 state）

---

## 与其他文档的关系

- 本文件覆盖 `goals-duty.md` 中所有 8 条 Duty 的可测试行为。
- 本文件中的 Critical Scenarios 对应 `dfd-interface.md` 中的 6 条数据流。
- 本文件中的 Integration Points 对应 `use-case.md` 中 UC-1 至 UC-10 的接缝处。
- 若 Duties 或数据流调整，本文件需同步更新；测试不能成为变更阻碍，仅是行为契约。
