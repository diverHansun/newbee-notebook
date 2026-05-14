# goals-duty.md — explain-mode-ui

## 模块定位（一句话）

重塑文档阅读器中"解释 / 总结"浮卡的视觉、流式与等待体验：去除黄色品牌色与"卡片嵌套"观感，让容器隐形而内容主导；同时把 `fixed + ResizeObserver + MutationObserver + rAF` 这套定位追踪改为 `position: absolute` 子节点，删除约 30 行同步代码。

本批次**不重写**入口 pill、不接入引用来源、不实现对话记录式回溯——这些划入未来批次。

---

## 一、Design Goals（设计目标）

1. **容器隐形化**：浮卡视觉权重必须低于其内容；标题栏、边框、阴影应"恰好可辨"。借鉴 Apple / OpenAI 桌面浮层语言：无强调色块、无渐变、依靠空气感与轻阴影，让 AI 回答本身成为主角。

2. **流式呈现平滑化**：用户感知到的内容输出节奏必须接近人眼可读速度，避免后端单次大块 delta 造成的"瞬间贴出整段"。复用 chat 链路已验证的 `markdown-typewriter` 切片机制，**不重新发明节流**。

3. **等待状态零认知负担**：首 token 之前的等待 UI 只表达"正在工作"一件事，不暴露后端阶段细节（`reasoning` / `retrieving` / `synthesizing` 三态后端已在发，本批次刻意不消费）。采用 OpenAI 风格的黑点呼吸——尺度与不透明度变化承担"活着"语义，文字不参与。

4. **错误与正文严格分离**：错误事件不再以 `[E_STREAM] xxx` 形式被拼接进 markdown 内容，改为独立结构呈现（错误图标、独立色彩、明确"重试"动作）。

5. **模式切换的连续性**：同一张卡片上从"解释 A 段"切到"总结 B 段"，应有 150ms opacity 过渡，避免内容硬切。

6. **定位机制收敛**：浮卡不再通过 fixed + ResizeObserver + MutationObserver + rAF 追踪 Main 面板矩形，改为 Main 面板的 positioned 子节点（`position: absolute`），布局变化由 CSS 自然承担。

7. **入口零回归**：右上角 pill 的视觉位置、文字、点击行为不变，本批次不动它（实现侧仅改挂载父节点，用户不可见）。

8. **可逆性**：所有视觉变更收敛到一个局部 CSS 变量 `--explain-accent`（淡紫色）与本模块的 7 个组件文件；回滚成本仅限本目录，不影响 chat / ask / Reader / Studio。

---

## 二、Duties（职责）

本批次需完成且仅完成以下职责：

### 1. 卡片视觉重构（去黄、淡紫单色）

- 标题栏移除黄色 `border-left: 3px` 与黄色渐变背景；改为**淡紫色单一强调色** `--explain-accent`。
- 模式标识改为"小点 + 纯文字"：小点 6px 圆点用 `--explain-accent`；文字"解释" / "总结"用 `--foreground`；不再使用 `badge-explain` / `badge-conclude` 颜色胶囊类，**explain 与 conclude 共用同一个淡紫色**（不区分）。
- 选中文本从标题栏移到 body 顶部，作为引用块展示（左 2px 灰竖线 + 极轻灰底，完整可读，不再 `max-width: 160px` 省略）。
- 操作区只保留"折叠"图标按钮（lucide SVG），不引入 ✕ 关闭。
- 容器外框 `1px solid hsl(var(--border) / 0.6)` + 柔和大阴影 `0 12px 32px -8px rgba(0,0,0,0.12)`；背景纯色无渐变。
- 拖拽 / 缩放手柄默认透明（opacity 0），hover 才浮现到 0.5。
- 空态：上方一个轻量 SVG 图示（引用符号或简单线稿），下方两行提示文字；不放 emoji。

### 2. 流式输出接入打字机

- 新增 `useTypewriterBuffer` hook，封装"原始 delta 累积 → 节流暴露可见字符 → flush"三步。
- 在 `useChatSession.ts` 的 explain 分支中，将 SSE `content` 事件的 `delta` 推入该 buffer，由 buffer 按帧节流（16-32ms 步长）喂给 `appendExplainContent`。
- SSE `done` 事件触发 `buffer.flush()`，把剩余字符一次性吐完。
- SSE `error` 与网络中断也必须 flush，避免残留未暴露字符。

### 3. 等待 UI 改为黑点呼吸

- 删除现有 `.streaming-dot` 黄色脉冲 + "加载中…"文案的并排展示。
- 新增 `ExplainCardLoader` 组件：单圆点，浅色模式 `hsl(220 10% 25%)`、深色模式 `hsl(220 5% 90%)`（具体值与理由见 `non-functional.md` §4.3）；`@keyframes` 控制 `transform: scale(0.55 → 1.0 → 0.55)` + `opacity: 0.35 → 1 → 0.35`，周期约 1.4s，`ease-in-out infinite`，居中独占 body 空间。
- 仅当 `isStreaming === true && content === "" && error === null` 时显示；首 token 到达即让位给打字机内容。

### 4. 错误状态独立块

- 扩展 `ExplainCardState` 增加 `error: ExplainCardError | null` 字段。
- explain 分支在 SSE `error` 或网络异常时不再 `appendExplainContent` 拼接错误码到 markdown，改为 `setExplainError({code, message, retryable})`。
- body 在 `error !== null` 时渲染 `ExplainCardError` 块：淡红 1px 边框、错误图标 SVG、错误文案、"重试"按钮。
- 点击"重试"→ 清空 `error`、重发上次请求；error 期间已生成的 `content` 不被覆盖（用户仍可读已生成部分）。

### 5. 模式切换淡入

- 检测 `card.mode` 或 `card.selectedText` 变化时，body 走 150ms opacity 0→1。
- 实现：在 body 包装层绑 `key={lastInteractionKey}`，React 卸载重挂 + CSS `@keyframes fade-in`，避免手写过渡时序。

### 6. 浮卡定位重构

- 删除 `explain-card.tsx` 中的 `anchorRect` state、`updateAnchor` rAF 逻辑、`ResizeObserver`、`MutationObserver`、`window.addEventListener("resize", ...)` 五处（约 33 行）。
- 把 `ExplainCard` 从 `createPortal(document.body)` 改为渲染在 `#main-panel-section` 内部。
- 给 `#main-panel-section` 加 `position: relative`（已是布局子项，加这一条不影响外部）。
- pill 与卡片均用 `position: absolute; top: 8px; right: 8px;`；用户拖拽时只动 `transform: translate(x,y)`，不动 `top` / `right`。
- pill 的 `z-index` 略低于卡片（pill `1` / 卡片 `2`），同时仍高于 Main 面板内的滚动内容。

### 7. i18n 完备（zh + en）

在 `uiStrings.explainCard` 下新增 / 调整以下 key（zh / en 双值）：

| key | zh | en |
|---|---|---|
| titleExplain | 解释 | Explain |
| titleConclude | 总结 | Summarize |
| titleDefault | 解释 / 总结 | Explain / Summarize |
| quotedTextLabel | 选中文本 | Selected text |
| emptyTitle | 还没有内容 | Nothing yet |
| emptyHint | 在文档中选中一段文字，然后点击"解释"或"总结" | Select text in the document, then click Explain or Summarize |
| loading（保留） | 正在生成 | Generating |
| error.title | 生成失败 | Generation failed |
| error.retry | 重试 | Retry |
| error.generic | 出现了点问题，请重试 | Something went wrong, please retry |
| expandTitle / collapseTitle / clickToExpand（保留） | … | … |

### 8. 测试覆盖

- `useTypewriterBuffer` 单测：累积、节流、flush、reset。
- explain 分支错误事件 → store.error 转换的 hook 测试。
- `ExplainCard` 五态渲染断言（RTL）：empty / loading / streaming / done / error。
- 模式切换：mode 变化触发 body key 变化、fade-in 出现。
- 重构定位的回归断言：pill 与卡片均挂在 `#main-panel-section` 内部。

---

## 三、Non-Duties（刻意排除）

1. **不接入后端 `sources` 事件**
   - 后端 SSE 已发引用来源（`type: "sources"`），本批次不在浮卡中展示。留待"对话记录式回溯改造"统一接入。

2. **不实现对话记录式可回溯消息条**
   - 用户期望的下一步演化方向（卡片内可往上翻看历史解释 / 总结）属于独立批次。本批次只做单卡片替换 + opacity 淡入淡出。

3. **不修改 `SelectionMenu`**
   - 现有 `💡 解释` / `📝 总结` / `🔖 标记` 三个 emoji 保持不变；该组件本批次不动。

4. **不持久化拖拽位置**
   - 每次重开卡片仍 `resetPosition({x:0, y:0})`，这是有意的，不写入 store / localStorage。

5. **不新增 ✕ 关闭按钮**
   - 卡片只能折叠回 pill，不能彻底关闭；与现有交互模型一致。

6. **不消费 `phase` / `warning` 事件**
   - 后端已发 `reasoning` / `retrieving` / `synthesizing` 三态，但本批次刻意不展示阶段进度——黑点呼吸覆盖了"未到首 token"的全部认知需求。决策保留可逆性：事件已在路上，未来若产品需要标签化阶段，前端只需新增订阅。
   - `warning` 同理，避免与错误块语义混淆。

7. **不重构 `useChatSession` 整体**
   - 仅在其 explain 分支（约 1320–1450 行）做最小改动：换 typewriter buffer、加 error 分流。chat / ask 分支不动。

8. **pill 不改**
   - 视觉、文字、位置、点击行为完全保持现状；唯一变化是其挂载父节点从 `document.body` 改为 `#main-panel-section`，用户不可见。

9. **不引入新的全局视觉颜色 token**
   - 仅新增一个局部 CSS 变量 `--explain-accent`（淡紫色），声明于本模块 CSS 节内，深色模式提供降饱和变体。不污染 `globals.css` 的全局色板。

10. **不支持窄屏全宽贴底布局**
    - 本批次保留现有的"右上角浮卡"形态；移动端 / 窄屏（<480px）的全屏化布局留待响应式改造批次处理。

---

## 四、与其他文档的关系

- 本文件是 `docs/frontend-v3/explain-mode-ui/` 设计文档集的边界声明。
- `architecture.md` / `data-model.md` / `dfd-interface.md` / `use-case.md` / `non-functional.md` / `test.md` 必须以本文件为前提。
- 若实施过程中发现需要超出 Duties 的能力，必须先回到本文件讨论调整，而不是在下游文档中"扩职责"。
