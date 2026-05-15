# architecture.md — explain-mode-ui

## 撰写前置确认

- `goals-duty.md` 已锁定本批次边界：视觉轻量化、typewriter buffer、错误与正文分离、定位收敛、i18n 与测试。
- 本文件采用实施中确认的轻量方案：**Point Extension + Local Render Helpers**，不再把卡片拆成多个 presentational 组件文件。

---

## 一、Architecture Overview（总体架构）

explain-mode-ui 是一个纯前端模块，跨三层但不引入独立组件目录：

1. **事件消费层：`useChatSession.ts` 的 explain / conclude 分支**
   - 位置：`frontend/src/lib/hooks/useChatSession.ts`。
   - 只改 explain / conclude 分支：SSE `content` 推入 `useTypewriterBuffer`，`done` / `error` / 网络 fallback 前 flush。
   - 错误不再拼进 markdown；统一写入 `explainCard.error`。
   - 保存最近一次 explain / conclude 请求，暴露 `retryExplainCard()` 给视图层。

2. **节流层：`useTypewriterBuffer.ts`**
   - 位置：`frontend/src/lib/hooks/useTypewriterBuffer.ts`。
   - 职责：把原始 SSE delta 累积成 raw content，再按 rAF 节奏把可见增量交给 `appendExplainContent`。
   - 复用 `markdown-typewriter` 的 visible map，避免在 markdown 标记中间切断。

3. **状态层：`chat-store.explainCard`**
   - 位置：`frontend/src/stores/chat-store.ts`。
   - `ExplainCardState` 扩展 `error` 与 `lastInteractionKey`。
   - 提供 `setExplainError` / `clearExplainError`；`buildExplainInteractionKey(mode, selectedText)` 负责生成 body fade-in key。

4. **视图层：`ExplainCard` 单文件宿主**
   - 位置：`frontend/src/components/chat/explain-card.tsx`。
   - 保留一个宿主组件，内部用小的本地 helper / render branch 处理 title、quote、loader、empty、error、markdown content。
   - 不新增 `ExplainCardBody` / `ExplainCardLoader` / `ExplainCardError` 等独立文件；这些分支只服务此卡片，生命周期也完全跟宿主一致，抽文件会增加维护成本。

5. **布局与样式：`reader.css` 第 21 节**
   - pill 挂在 `#main-panel-section` 内部，`position: absolute; top: 8px; right: 8px`（跟随 Main 面板布局）。
   - 展开卡片同样挂在 `#main-panel-section` 的 React 树内（无 Portal），但 `position: fixed`。初始 `top` / `right` 由 `ExplainCard` 在展开瞬间读 `#main-panel-section.getBoundingClientRect()` 一次得出并以 inline style 写入，之后 `transform: translate(x,y)` 跟随拖拽。`window.resize` 时重算一次。
   - 选择 fixed 是为了让卡片能跨越 Sources / Main / Studio 三栏拖拽——`<main>` 上的 `overflow: hidden` 会裁切 absolute 子节点，fixed 子节点的 containing block 是 viewport，可逃出。
   - CSS 只做必要减法：去掉展开卡片黄色渐变和左黄边；保留 pill 的既有外壳轮廓（淡边框 + 圆角），但 pill 内部不再嵌 `badge-*` 黄色胶囊；新增简单 quote / loader / error / 模式文字色样式。

---

## 二、Data Flow（核心数据流）

```
SelectionMenu
  -> useChatSession.sendMessage(mode="explain"|"conclude")
  -> setExplainCard({ content:"", isStreaming:true, error:null, lastInteractionKey })
  -> SSE content
  -> useTypewriterBuffer.push(delta)
  -> appendExplainContent(visibleDelta)
  -> ExplainCard render branch
```

终止与异常：

- `done`：`flush()` 剩余内容，`isStreaming=false`，`error=null`。
- SSE `error`：`flush()`，`isStreaming=false`，`error={code,message,retryable:true}`。
- 网络中断：先保留既有 persisted reply / `chatOnce` fallback；都失败才写入 `error`。
- retry：`clearExplainError()` 后调用 `retryExplainCard()`，复用最近一次 message / mode / context / sourceDocumentIds。

---

## 三、Design Pattern & Rationale（模式与理由）

### 1. Point Extension 优先

`ExplainCard` 原本就是一个小型浮层宿主，折叠、拖拽、缩放、模式标题、内容分支都共享同一生命周期。错误块、loader、empty state 没有复用场景，因此采用本地 helper 比拆 5 个文件更清晰。

这个判断与 `docs/frontend-v3/llm_title_aided/architecture.md` 中的 Point Extension 原则一致：当新增 UI 的生命周期与宿主完全一致，抽出独立组件通常会让实现失焦。

### 2. Hook Composition 保留

`useTypewriterBuffer` 独立存在，因为它是纯逻辑、可单测、与视图无关；这类抽象能降低 `useChatSession` 的复杂度。

### 3. CSS 简洁

本批次不建立新的视觉系统，不新增复杂 class family。样式只覆盖 explain card 第 21 节：

- pill 保持淡边框 + 圆角外壳，但**移除内层 `badge-*` 黄色胶囊**；文字按 mode 上色（explain 淡紫、conclude 淡青、default 中性灰）。
- 展开卡片改为中性边框、纯色标题栏、按 mode 上色的小点与文字。
- error / loader / quote 使用最少必要样式。

### 4. 不使用 Portal；展开卡片用 fixed 定位

`ExplainCard` 直接作为 `#main-panel-section` 的子节点在 React 树中渲染，不走 `createPortal`。

- pill：`position: absolute`，跟随 Main 面板布局变化，不需要 observer。
- 展开卡片：`position: fixed`。这是有意的——`<main>` 元素带 `overflow: hidden`，absolute 子节点会被裁切（无法拖出 Main 面板），fixed 子节点的 containing block 是 viewport，可以拖到 Sources / Studio 任意位置。初始锚点 `top` / `right` 在卡片展开瞬间从 Main 面板 rect 读一次得出，并随 `window.resize` 重算；不需要 `ResizeObserver` / `MutationObserver` / rAF 三件套。
- 用户拖拽时只动 `transform: translate(x, y)`，不动 inline 的 `top` / `right`——保持初始锚点稳定，重新展开时回到原位。

---

## 四、Module Structure & File Layout（模块结构）

```
frontend/src/
├── components/chat/
│   └── explain-card.tsx              # 单文件宿主：折叠、拖拽、状态分支渲染
├── components/notebooks/
│   └── notebook-workspace.tsx        # 将 retryExplainCard 传给 ExplainCard
├── lib/hooks/
│   ├── useChatSession.ts             # explain/conclude 分支接 buffer、error、retry
│   └── useTypewriterBuffer.ts        # 新：markdown-safe typewriter buffer
├── stores/
│   └── chat-store.ts                 # ExplainCardState 扩展
├── styles/
│   └── reader.css                    # 第 21 节轻量样式
└── lib/i18n/
    └── strings.ts                    # explainCard i18n key
```

---

## 五、Architectural Constraints & Trade-offs（约束与权衡）

1. **接受单文件宿主略大一点**
   - 代价：`explain-card.tsx` 保留多个本地渲染分支。
   - 收益：减少文件跳转，避免为无复用价值的 UI 状态建立组件层级。

2. **保留独立 buffer hook**
   - 代价：chat final typewriter 与 explain typewriter 仍是两套实现。
   - 收益：生命周期不同，避免把 chat message id 语义带进 explain card。

3. **不消费 phase / sources / warning**
   - 与 `goals-duty.md` 的 Non-Duties 保持一致。

4. **pill 不做重设计**
   - 本批次只改变挂载父节点和定位方式；视觉上尽量维持用户熟悉的入口。

---

## 六、自检结论

- 当前结构比原 6 个子组件方案更贴合实际规模。
- 关键行为仍有清晰边界：`useChatSession` 管业务状态，`useTypewriterBuffer` 管节奏，`ExplainCard` 只负责本地 UI 分支。
- 后续如果要做“历史解释 / 总结消息条”，再重新评估组件拆分；本批次不提前为未来复杂度买单。
