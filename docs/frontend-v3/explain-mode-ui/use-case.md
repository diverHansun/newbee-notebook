# use-case.md — explain-mode-ui

## 撰写前置确认

- `goals-duty.md` 已锁定 Duties 与 Non-Duties。
- `dfd-interface.md` 已描述 6 条主要数据流。
- 本文件中的每个用例均映射到 `dfd-interface.md` 中的具体数据流。

---

## 一、用例总览

| ID | 名称 | 主路径 / 备选 | 关联数据流 | 关联 Duty |
|---|---|---|---|---|
| UC-1 | 解释一段文档文本 | 主 | 流 1 | Duty 1, 2, 3 |
| UC-2 | 总结一段文档文本 | 主 | 流 1 | Duty 1, 2, 3 |
| UC-3 | 切换模式（同一卡片复用） | 主 | 流 2 | Duty 5 |
| UC-4 | 流式过程中出错 + 重试 | 异常 | 流 3 | Duty 4 |
| UC-5 | 网络中断 + 后端持久化 fallback | 异常 | 流 4 | Duty 4 |
| UC-6 | 折叠卡片回 pill | 主 | 流 5 | Duty 1 |
| UC-7 | 重新展开 pill 查看上次结果 | 主 | 流 5 | Duty 1 |
| UC-8 | 拖拽 / 缩放浮卡 | 辅 | 流 6 | （保持现状） |
| UC-9 | 空态：未选文本直接点 pill | 边界 | — | Duty 1 |
| UC-10 | 拖拽后折叠再展开（位置复位） | 边界 | 流 6 | Non-Duty #4 |

---

## 二、UC-1 解释一段文档文本

### 触发条件

用户在 `DocumentReader` 中选中一段文本，`SelectionMenu` 浮现。

### 主路径

1. 用户点击 SelectionMenu 的"💡 解释"按钮（emoji 保持现状，Non-Duty #3）。
2. 浮卡 pill 已存在于 Main 面板右上角；点击后立即展开（或如已展开则直接接收新内容）。
3. 卡片 body 进入 loading 态：**居中黑点呼吸**（`scale 0.55↔1.0` + `opacity 0.35↔1`，周期 1.4s）。
4. 卡片标题栏显示"● 解释"（淡紫小点 + 中性文字）。
5. body 顶部显示"选中文本"引用块（左 2px 灰竖线 + 极轻灰底，完整原文，不省略）。
6. 后端首 token 到达：黑点呼吸消失，typewriter 开始以约 24ms 步长、每 tick 最多 3 个可见字符的节奏推进内容。
7. 用户观察到内容逐字呈现，节奏接近"快速阅读"。
8. SSE `done` 到达：buffer flush 残余字符；流式状态结束；卡片保持展开。

### 预期结果

- 卡片内容 = 后端最终回复全文。
- 没有"[E_STREAM] ..."类错误码混在内容里。
- 拖拽手柄、缩放手柄、折叠按钮可正常使用。

### 触发的 Duties

Duty 1（视觉重构）/ Duty 2（typewriter）/ Duty 3（黑点呼吸）/ Duty 6（absolute 定位）。

---

## 三、UC-2 总结一段文档文本

### 触发条件 / 主路径

与 UC-1 同，仅区别：

- 用户点击"📝 总结"。
- 标题栏显示"● 总结"——**与 UC-1 用同一个淡紫色**（Architecture 决策 5）。
- 后端走 `mode=conclude` 路径，返回总结性内容。

### 预期结果

视觉上 UC-1 与 UC-2 仅文字标签差异，色彩完全一致。色觉障碍用户依赖"解释" / "总结"文字与引用块原文判别。

---

## 四、UC-3 切换模式（同一卡片复用）

### 触发条件

卡片已展示 UC-1 的"解释 A 段"结果，用户在文档中选中 B 段（或同一段），点击"📝 总结"。

### 主路径

1. `useChatSession.sendMessage(mode="conclude", ...)` 被触发。
2. `setExplainCard({...overwrite, content: "", error: null, lastInteractionKey: hash("conclude", newText)})`。
3. `ExplainCard` body 容器的 React `key` 变化 → 旧 body 卸载、新 body 挂载。
4. 新 body 容器执行 CSS `@keyframes fade-in`（150ms opacity 0→1）。
5. body 内部立即进入 loading 态（黑点呼吸）。
6. 后续步骤同 UC-1 [6]–[8]。

### 预期结果

- 用户**不会看到**两次内容拼接或硬切换。
- 标题栏从"● 解释"切到"● 总结"无明显闪烁（标题栏不重挂，仅模式文字字符变化）。
- 引用块从旧文本切到新文本。

### 触发的 Duties

Duty 5（模式切换淡入）。

---

## 五、UC-4 流式过程中出错 + 重试

### 触发条件

UC-1 / UC-2 进行中，SSE 收到 `event.type === "error"`，或 fetch 抛错且非"已收到 done"。

### 主路径

1. `useTypewriterBuffer.flush()` —— 把已累积但未暴露的字符立即吐出。
2. `setExplainError({code, message, retryable: true})`。
3. `ExplainCard` 检测到 `error !== null`：
   - **优先渲染本地 error block**，覆盖 loader（即使 isStreaming 残值为 true）。
   - 已有 `content` 不被覆盖——错误块出现在 body 中上部，content 已生成部分在错误块下方仍可见。
4. 错误块内含淡红 1px 边框、错误图标 SVG、文案、"重试"按钮。
5. 用户点击"重试"：
   - `clearExplainError()` 清错误。
   - 调用 `useChatSession` 持有的"上次请求重发"闭包，使用原 message / mode / context 重发。
   - 卡片回到 UC-1 [3] 起的 loading 态——黑点呼吸再次出现。
6. 重试成功：流程同 UC-1。
7. 重试再次失败：回到本用例 [2]。

### 备选路径 A：用户折叠后再展开

- 折叠不清错误。
- 重新展开 pill 时仍看到错误块；可继续点重试。

### 备选路径 B：用户在错误状态下选中新文本

- 触发新的 sendMessage → 整体覆盖（含 error: null）→ 进入 UC-1 / UC-2 / UC-3 流程。

### 预期结果

- 内容区**永远不出现** `[E_STREAM] ...` 字样。
- 错误图标、文案、"重试"按钮均走 i18n。
- 重试按钮在 `retryable === false` 时不渲染（本批次默认 true，留扩展位）。

### 触发的 Duties

Duty 4（错误状态独立块）。

---

## 六、UC-5 网络中断 + 后端持久化 fallback

### 触发条件

UC-1 进行中，浏览器丢网；SSE 连接断开，没有收到 `done` 也没有 `error` 事件，`fetch.onError` 回调被触发。

### 主路径

1. `shouldAttemptStreamFallback(error)` 判断为 true（既有逻辑，本批次保留）。
2. `findRecentPersistedAssistantReply(...)` 查询后端是否已持久化本次 assistant reply。
3. **命中**：
   - `setExplainCard(prev => ({...prev, content: persistedReply.content, isStreaming: false, error: null}))`。
   - 用户看到"完整内容直接出现"——**不再走 typewriter**（因为是 fallback，不模拟流式）。
   - 黑点呼吸消失，错误块不出现。
4. **未命中**：
   - 退回 `chatOnce` 一次性请求。
   - 成功 → 同上。
   - 失败 → `setExplainError({code: "E_NETWORK", message: t("explainCard.error.generic")})`，进入 UC-4 错误态。

### 预期结果

- 大多数网络抖动用户感知为"等待略长"，但最终看到完整内容。
- 仅当 fallback 也失败才暴露错误块。

---

## 七、UC-6 折叠卡片回 pill

### 触发条件

卡片处于展开状态，用户点击标题栏右侧的折叠图标按钮。

### 主路径

1. `setCollapsed(true)`。
2. `ExplainCard` 内部条件分支改为渲染 pill（不重置 store 中 explainCard 状态）。
3. pill 显示在 Main 面板右上角（absolute 子节点，无视觉跳动）。
4. pill 的标签：
   - 若 `explainCard === null` → "解释 / 总结"（titleDefault）
   - 若 `explainCard.mode === "explain"` → "解释"
   - 若 `explainCard.mode === "conclude"` → "总结"
5. 若 `isStreaming === true`，pill 右侧显示"加载中…"小提示与小点（保持现状，pill 不动 Duty 7）。

### 预期结果

- 折叠不打断流式：后端 SSE 继续到达，buffer 仍在 tick；用户重展开后能看到已生成内容。
- pill 视觉、位置、文字逻辑与本批次前完全一致。

---

## 八、UC-7 重新展开 pill 查看上次结果

### 触发条件

pill 可见（含或不含上次结果），用户点击 pill。

### 主路径

1. `setCollapsed(false)`。
2. 卡片渲染：
   - 若 `explainCard !== null` → 渲染 body（含已有 content / loader / error）。
   - 若 `explainCard === null` → 渲染**空态**：提示用户在文档中选中文本后再解释 / 总结。
3. 不触发 fade-in（`lastInteractionKey` 未变）。

### 预期结果

- 用户上次的解释 / 总结结果仍可读，不会因折叠丢失。
- 空态出现仅在用户从未触发过 explain / conclude 时。

---

## 九、UC-8 拖拽 / 缩放浮卡

### 主路径

1. 用户在标题栏区域 `pointerdown`，按住拖动 → 卡片 `transform: translate(x, y)` 跟随。
2. 用户在卡片右下角 `pointerdown`，按住拖动 → 卡片 width / height 变化（受 `useResizable` minSize / maxSize 约束：380×400 ~ 720×900）。
3. 拖拽 / 缩放期间 box-shadow 过渡禁用（避免性能开销，既有逻辑保留）。

### 预期结果

- 拖拽手柄默认不可见，hover 时 opacity 升到 0.5。
- 拖拽中卡片不会脱离视口（既有 `boundedHeight` 保护，本批次保留）。

---

## 十、UC-9 空态：未选文本直接点 pill

### 触发条件

用户从未触发过 explain / conclude（`explainCard === null`），但 pill 仍渲染（因为标签默认是"解释 / 总结"，pill 持续存在——保持现状 Duty 7）。

### 主路径

1. 用户点击 pill → `setCollapsed(false)`。
2. 卡片打开。
3. body 渲染空态：
   - 下方两行提示文字：
     - 主文案 "还没有内容"（i18n `emptyTitle`）。
     - 辅文案 "在文档中选中一段文字，然后点击解释或总结"（i18n `emptyHint`）。
4. 标题栏显示"● 解释 / 总结"（淡紫小点 + 中性文字 titleDefault）。
5. 用户可关闭、可拖拽，但内容区无可交互内容。

### 预期结果

- 不出现 emoji。
- 不出现"加载中"或错误提示。

---

## 十一、UC-10 拖拽后折叠再展开（位置复位）

### 触发条件

用户拖拽卡片到非默认位置，然后折叠，再展开。

### 主路径

1. 拖拽过程中 `position` state 变化，卡片视觉跟随。
2. 用户点击折叠 → `setCollapsed(true)`。
3. 用户点击 pill 重展开 → `setCollapsed(false)` + `resetPosition({x: 0, y: 0})` 触发。
4. 卡片回到默认位置（右上角 + 默认 size）。

### 预期结果

- 位置不持久化（Non-Duty #4）；用户的拖拽偏移不跨"折叠"保留。
- 这是有意设计——多次拖拽 + 折叠 + 重展开能让用户回到"已知位置"，避免卡片"漂"到屏幕边缘。

---

## 十二、用例与 Duty / Non-Duty 的覆盖矩阵

| Duty | 涉及用例 |
|---|---|
| Duty 1 视觉重构 | UC-1, UC-2, UC-6, UC-7, UC-9 |
| Duty 2 typewriter | UC-1, UC-2 |
| Duty 3 黑点呼吸 | UC-1, UC-2, UC-3, UC-4（重试后回到此态） |
| Duty 4 错误独立块 | UC-4, UC-5（未命中分支） |
| Duty 5 模式切换淡入 | UC-3 |
| Duty 6 absolute 定位 | UC-6, UC-7（所有用例隐含，但折叠/展开最能体现） |
| Duty 7 i18n | UC-4（error 文案）, UC-9（空态文案） |

| Non-Duty | 体现用例 |
|---|---|
| ND-1 不接 sources | 全用例（不展示引用） |
| ND-2 不实现对话记录 | 全用例（仅单卡片） |
| ND-3 不改 SelectionMenu | UC-1, UC-2（emoji 仍在） |
| ND-4 不持久化拖拽 | UC-10 |
| ND-5 不加 ✕ 关闭 | UC-6（只有折叠按钮） |
| ND-6 不消费 phase | UC-1（loading 期间无阶段标签） |
