# architecture.md — explain-mode-ui

## 撰写前置确认

- `goals-duty.md` 已存在并以"模块定位 + 8 条 Design Goals + 8 条 Duties + 10 条 Non-Duties"形式锁定边界。
- 本文件描述的所有结构均可追溯到既定 Design Goals 与 Duties；未引入新职责。

---

## 一、Architecture Overview（总体架构）

explain-mode-ui 是一个**纯前端模块**，跨"事件消费层 / 状态层 / 视图层"三层但全部位于浏览器进程内。子组件如下：

### 事件消费层

1. **useChatSession (explain 分支)** — 既有
   - 位置：`frontend/src/lib/hooks/useChatSession.ts`，约 1320–1450 行。
   - 本批次只**修改**该分支：把 `appendExplainContent(event.delta)` 改为推到 typewriter buffer；把 `appendExplainContent(\`[errorCode] ...\`)` 改为 `setExplainError({...})`。
   - 不抽出新的 hook，避免破坏 chat / ask 路径的耦合契约。

2. **useTypewriterBuffer (新)**
   - 位置：`frontend/src/lib/hooks/useTypewriterBuffer.ts`。
   - 职责：维护"原始累积 delta + 当前可见字符数"，按帧（rAF）以 16-32ms 步长把可见字符喂给消费方；`flush()` 一次性吐完。
   - 与 chat 路径的"final typewriter"逻辑**不抽公共层**——chat typewriter 与 message id 强绑定、且与 `stopFinalTypewriterForMessage` 配套；explain 的语义是"单卡片 buffer"，强行抽公共层只会引入两组无意义的参数。增量太小，**Composition over abstraction**。

### 状态层

3. **chat-store.explainCard (扩展)**
   - 位置：`frontend/src/stores/chat-store.ts`。
   - 扩展 `ExplainCardState`：新增 `error: ExplainCardError | null`、`lastInteractionKey: string`。
   - 新增 action：`setExplainError`、`clearExplainError`、`bumpExplainInteractionKey`。

### 视图层

4. **ExplainCard (容器，重写)**
   - 位置：`frontend/src/components/chat/explain-card.tsx`。
   - 改造点：删除 `anchorRect` / ResizeObserver / MutationObserver / rAF 追踪逻辑；删除 `createPortal(document.body)`，直接渲染为 `#main-panel-section` 内部的 absolute 子节点。
   - 仅承担"挂载位置、折叠/展开状态、拖拽/缩放手柄绑定"三件事；不持有内容、错误、加载等业务状态——这些由 store 提供。

5. **ExplainCardTitleBar (新)**
   - 位置：`frontend/src/components/chat/explain-card-titlebar.tsx`。
   - 渲染"模式小点 + 模式文字 + 折叠按钮"；onPointerDown 用于拖拽。
   - 不再渲染选中文本（移至 body）。

6. **ExplainCardBody (新)**
   - 位置：`frontend/src/components/chat/explain-card-body.tsx`。
   - 内容分发器：依据 `(content, isStreaming, error)` 三元组选择渲染分支：
     - `error !== null` → `<ExplainCardError />`
     - `content === "" && isStreaming` → `<ExplainCardLoader />`
     - `content === "" && !isStreaming` → `<ExplainCardEmptyState />`
     - 其他 → `<SelectedTextQuote />` + `<MarkdownViewer content={content} />`
   - 包装层绑 `key={lastInteractionKey}` 触发模式切换 fade-in。

7. **ExplainCardLoader (新)**
   - 位置：`frontend/src/components/chat/explain-card-loader.tsx`。
   - 黑点呼吸；纯 CSS 动画。

8. **ExplainCardError (新)**
   - 位置：`frontend/src/components/chat/explain-card-error.tsx`。
   - 渲染错误图标 + 文案 + "重试"按钮；按钮回调由 props 注入（来自 useChatSession 的重发函数）。

9. **ExplainCardEmptyState (新)**
   - 位置：`frontend/src/components/chat/explain-card-empty-state.tsx`。
   - SVG 图示 + 两行提示文字。

10. **SelectedTextQuote (新，内联到 body 文件内)**
    - body 顶部的引用块，展示用户选中原文。

### 子组件协作关系

```
用户选中文本 → SelectionMenu (不动)
                 │
                 ▼
        useChatSession.sendMessage(mode="explain"|"conclude")
                 │
                 ▼
        SSE 流式事件
        ┌─────────┼──────────┬─────────┐
        ▼         ▼          ▼         ▼
      start    content      error     done
        │       │            │         │
        │       ▼            ▼         ▼
        │  useTypewriterBuffer  setExplainError  flush()
        │       │            │
        │       ▼            │
        │  appendExplainContent (受节流)
        │       │            │
        ▼       ▼            ▼
        chat-store.explainCard (visible/content/error/isStreaming/lastInteractionKey)
                 │
                 ▼
        ExplainCard (absolute child of #main-panel-section)
            ├── ExplainCardTitleBar
            └── ExplainCardBody (key=lastInteractionKey)
                    ├── ExplainCardError (if error)
                    ├── ExplainCardLoader (if streaming & empty)
                    ├── ExplainCardEmptyState (if !streaming & empty)
                    └── SelectedTextQuote + MarkdownViewer (otherwise)
```

---

## 二、Design Pattern & Rationale（设计模式与理由）

### 1. Container / Presentational Split

`ExplainCard` 是 Container（持有挂载位置、折叠/展开、拖拽），其余 `ExplainCardTitleBar` / `Body` / `Loader` / `Error` / `EmptyState` 是 Presentational（仅消费 props 与 store 状态）。

**为什么这样拆**：当前 `explain-card.tsx` 一个文件承担挂载、状态、视觉三件事，约 200 行；本批次的视觉重构、错误块、空态、loader 都属于"渲染分支"性质，集中到 body 分发器后各自独立，命名直白、单元测试容易。Container 文件压缩到约 80 行，仅剩"位置 + 折叠"两个关注点。

### 2. Hook Composition (useTypewriterBuffer)

把"原始累积 → 可见字符节流 → flush"封装为一个独立 hook，不耦合到 store 或 view。

**为什么不抽公共 typewriter 层**（与 chat 路径共享）：

- chat typewriter 绑定到具体 message id，并通过 `stopFinalTypewriterForMessage` 控制；explain 路径只有"单卡片单 buffer"语义，强行公共化要引入消息 id 概念。
- chat typewriter 的字符暴露是基于 message.content 整体更新，explain 路径基于 store.explainCard.content；两者的写入目标不同。
- 增量很小（buffer hook 约 60–80 行），**复用机会与维护成本不平衡**。Non-Duty 已声明不重构 useChatSession 整体。

### 3. Strategy 的轻量应用 (Body 内容分发)

`ExplainCardBody` 是一个 strategy switch：根据 `(content, isStreaming, error)` 选 4 个 presentational 之一。

**为什么不用单一组件 + 内部条件渲染**：4 个分支的视觉与 a11y 语义差异显著（loader 需 `aria-live="polite"`、error 需 `role="alert"`、empty 是普通静态内容），单组件内条件渲染会让 props / aria 属性混乱。Strategy 把分支显式化，每个 presentational 自己声明 a11y 语义。

### 4. CSS Variable Scoping (--explain-accent)

新增的淡紫色不进入全局 token，而是声明在本模块 CSS 段内：

```css
.explain-card {
  --explain-accent: hsl(270 60% 70%);  /* 淡紫，浅色模式 */
}
.dark .explain-card {
  --explain-accent: hsl(270 35% 60%);  /* 降饱和，深色模式 */
}
```

**为什么不放进 `globals.css` 的全局 token**：本批次的视觉颜色仅服务于一个组件树，未来如要替换或调整无需触动全局。这与 `goals-duty.md` 的"可逆性"目标一致。

### 5. 不使用 Observer / Pub-Sub for Position

放弃 `ResizeObserver` / `MutationObserver` / `requestAnimationFrame` 三件套追踪 Main 面板矩形的方案。

**为什么**：用 `position: absolute` 挂到 `#main-panel-section` 内部后，浏览器布局引擎本身就承担了"父节点变化 → 子节点重排"的职责；手工同步是多余的。删除约 33 行后没有可观测的视觉回归——pill 与卡片随 Main 面板自然摆放。

### 6. 不使用 Portal

放弃 `createPortal(document.body)`，直接在 React 树中渲染。

**为什么**：原方案使用 Portal 是因为 ResizeObserver 追踪 Main 面板矩形后用 fixed 定位；改 absolute 后 Portal 失去价值，反而引入"挂载点与 React 父子关系不一致"的心智负担。直接渲染让事件冒泡、CSS 继承、devtools 树视图都更自然。

---

## 三、Module Structure & File Layout（模块结构与文件组织）

```
frontend/src/
├── components/chat/
│   ├── explain-card.tsx                    # 重写：仅挂载/折叠/拖拽
│   ├── explain-card-titlebar.tsx           # 新：标题栏（模式点+文字+折叠）
│   ├── explain-card-body.tsx               # 新：body 分发器
│   ├── explain-card-loader.tsx             # 新：黑点呼吸
│   ├── explain-card-error.tsx              # 新：错误块
│   └── explain-card-empty-state.tsx        # 新：空态
├── components/notebooks/
│   └── notebook-workspace.tsx              # 修改：把 ExplainCard 从 mainOverlay 改为 mainInner
├── lib/hooks/
│   ├── useChatSession.ts                   # 修改：explain 分支接 typewriter buffer + setExplainError
│   └── useTypewriterBuffer.ts              # 新：节流 buffer hook
├── stores/
│   └── chat-store.ts                       # 修改：ExplainCardState 加 error / lastInteractionKey
├── styles/
│   └── reader.css                          # 重写第 21 节（explain card 样式）
└── lib/i18n/
    └── strings.ts                          # 扩展 explainCard 字段（zh/en）

docs/frontend-v3/explain-mode-ui/           # 本模块设计文档集
```

### 对外稳定接口

- `chat-store.useChatStore().explainCard`：字段语义对消费方稳定（扩展兼容，不破坏既有 `visible` / `mode` / `selectedText` / `content` / `isStreaming`）。
- `useChatSession.sendMessage(message, mode="explain"|"conclude", ...)`：签名不变。
- `MarkdownViewer`：仍由 body 调用，未做改动。

### 内部实现（不对外稳定）

- 6 个新组件的内部 DOM 结构与样式细节、`useTypewriterBuffer` 的内部 state shape、CSS 变量名 `--explain-accent` 的具体色值——这些可以在后续批次调整而不影响调用方。

---

## 四、Architectural Constraints & Trade-offs（约束与权衡）

### 1. 放弃 Portal + fixed 定位，换实现简单度

- **被放弃方案**：`createPortal(document.body)` + `position: fixed` + `ResizeObserver` 追踪 Main 面板矩形。
- **当前方案代价**：要求 `#main-panel-section` 设 `position: relative`；卡片的 z-index 范围与 Main 面板内其他浮层（如代码块复制按钮）有潜在冲突需检查。
- **理由**：删除约 33 行同步代码、消除三种 observer，未来 Main 面板布局变化不会引发"卡片追错位置"。

### 2. 放弃公共 typewriter 抽象，接受局部重复

- **被放弃方案**：把 chat 路径与 explain 路径的 typewriter 逻辑抽到公共 util。
- **当前方案代价**：chat 与 explain 各有一份"原始 → 可见字符"的暴露逻辑，未来如要改节流策略需改两处。
- **理由**：chat typewriter 与 message id 绑定，explain typewriter 与 explainCard 绑定；两者写入目标不同、生命周期不同；公共化要引入"buffer key"参数体系，复杂度高于一次重复实现。Non-Duty #7 明确不重构 useChatSession 整体。

### 3. 不消费 phase / sources / warning 事件

- **被放弃方案**：把后端已发的 `phase` / `sources` / `warning` 事件接入浮卡（阶段标签、引用来源列表、警告提示）。
- **当前方案代价**：等待期间用户看不到"现在在检索 / 在合成"等中间状态；引用来源在浮卡中不可见；warning 事件被静默丢弃。
- **理由**：goal #3 明确"等待状态零认知负担"——黑点呼吸覆盖了首 token 之前的全部需求；sources / warning 的展示属于"对话记录式回溯"未来批次的范围（Non-Duty #1、#2）。

### 4. 接受 ExplainCard 与 chat 消息分支并存的状态模型

- 当前 chat / ask 路径用 `messages[]` 数组，explain / conclude 路径用 `explainCard` 单对象。两者持久化语义不同（messages 入会话历史、explainCard 不入），暂不统一。
- 未来"对话记录式可回溯消息条"批次会重新审视——可能改为统一 messages 模型，或在 explain 维度做"消息序列"。本批次刻意不为这一未来设计买单。

### 5. 接受单一淡紫色，放弃 explain / conclude 颜色区分

- **被放弃方案**：explain 用淡蓝、conclude 用淡紫（或其他二色方案）。
- **当前方案代价**：两种模式视觉上仅靠"解释" / "总结"文字区分，色觉障碍用户也只能依赖文字。
- **理由**：goal #1 容器隐形化 + Apple/OpenAI 风格的核心是"消色"；引入二色会再次让容器抢戏。文字标签 + 一致字号已足够可辨。

---

## 五、自检结论

- 每个子组件存在的理由都可追溯到 Duties；6 个新组件均对应至少一条具体 Duty（视觉重构 / loader / error / empty / 模式切换 / typewriter）。
- 不存在为"优雅"而新增的抽象层（如 typewriter 公共基类、Card 基类）。
- 与既有 chat 视觉结构对称——chat 也用 Container / Presentational + Hook，本模块沿用而非创新。
