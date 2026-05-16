# non-functional.md — explain-mode-ui

## 撰写前置确认

- `goals-duty.md` / `architecture.md` / `dfd-interface.md` / `use-case.md` 已存在并已锁定边界。
- 本文件描述的非功能要求均不引入新职责，仅约束已确定 Duties 的实现方式。

---

## 一、性能 (Performance)

### 1.1 流式渲染节奏

| 指标 | 目标 | 测量方式 |
|---|---|---|
| typewriter step 间隔 | 16–32ms（默认 24ms） | hook 内 rAF 时间戳 |
| 每 tick 暴露字符数 | ≤ 3 个可见字符 | hook 配置常量 |
| 视图更新频率 | ≤ 60fps（rAF 自然限制） | DevTools Performance 面板观察 |

**理由**：低于 16ms 步长会浪费 GPU；高于 32ms 出现可感停顿。每 tick 最多 3 个可见字符，是为了让中文用户在 SSE 大块 delta 到达时也能感知到逐字滚动，而不是"嗖一下"。

### 1.2 黑点呼吸动画

| 指标 | 目标 |
|---|---|
| 动画属性 | `transform: scale(...)` + `opacity: ...` 双轨；不动 `width` / `height` / `box-shadow` |
| 帧率 | 浏览器主合成线程 60fps，CSS keyframes 由 GPU 合成 |
| CPU 占用 | < 1%（在 idle 浏览器中） |

**实现约束**：不可使用 JS 驱动的 `setInterval` / `setTimeout` 动画；必须用纯 CSS `@keyframes`。

### 1.3 模式切换 fade-in

| 指标 | 目标 |
|---|---|
| 时长 | 150ms |
| 缓动 | `ease-out`（开头快、结尾平稳） |
| 触发频率 | 仅在 `lastInteractionKey` 变化时；同一会话内的多次 token 不重触发 |

### 1.4 浮卡定位重构后的性能收益

- 删除 `ResizeObserver` / `MutationObserver` / `rAF` 持续同步三件套；只保留：(a) 展开瞬间一次 `getBoundingClientRect()` 读取，(b) 一个 `window.resize` listener。
- Main 面板拖动 / 三栏 resize 时不再触发 explain 卡片重定位 JS——pill 走 CSS 自然布局，展开卡片用户已主动拖拽过则保持当前位置。
- 浮卡 visibility 切换（折叠/展开）不再涉及 `createPortal` 的 detach/attach；React 树更小巧，devtools 中可读性提升。

### 1.5 内存

| 指标 | 目标 |
|---|---|
| typewriter buffer 内存峰值 | < 1MB（典型回答 5KB；buffer 仅持有累积字符串 + 索引数组） |
| 重新进入会话不泄漏 | unmount 时 `reset()` 清空 buffer，取消 rAF |

---

## 二、可访问性 (Accessibility)

### 2.1 ARIA 角色与活动区

| 元素 | role | aria-live |
|---|---|---|
| `ExplainCard` loader 分支 | `status` | `polite` |
| `ExplainCard` error block 分支 | `alert` | `assertive` |
| `ExplainCard` empty 分支 | （无） | （无） |
| `ExplainCard` 内容区 | `region` 或语义化容器 | `polite` |

**理由**：

- loader 用 `polite` 是因为加载状态不需要打断屏幕阅读器当前播报。
- error 用 `assertive` 是因为错误信息应立即打断。
- 内容区用 `polite` 让流式字符的暴露被无障碍读屏渐进读出（虽然字符级追加未必逐字读，但符合规范）。

### 2.2 键盘导航

- pill / 折叠按钮 / 错误块中的"重试"按钮均可通过 Tab 聚焦。
- pill 与卡片之间不形成键盘陷阱：Esc 键关闭卡片（折叠）。
- 拖拽 / 缩放手柄**不参与键盘导航**（拖拽是高级功能，键盘用户可不用）。

### 2.3 减少动画偏好

```css
@media (prefers-reduced-motion: reduce) {
  .explain-card-loader { animation: none; opacity: 0.7; }
  .explain-card-body-fade-in { animation: none; }
  /* typewriter buffer 仍按节奏暴露字符，但加速到 stepMs=4，charsPerTick=20 */
}
```

**理由**：完全禁用 typewriter 会让用户看到"瞬间出现整段"，反而与黑点呼吸 + 突然内容到达的视觉冲突更大；折中是大幅加速。

### 2.4 颜色对比度

| 元素 | 浅色模式 | 深色模式 | 目标 |
|---|---|---|---|
| 主文本 vs 卡片背景 | `--foreground` vs `--card` | 同 | ≥ 7:1 (AAA) |
| 引用块文本 vs 引用块底色 | `--foreground` vs `--muted/40%` | 同 | ≥ 4.5:1 (AA) |
| 淡紫色小点 vs 卡片背景 | `--explain-accent: hsl(270 60% 70%)` | `hsl(270 35% 60%)` | ≥ 3:1（非文字色块） |
| 错误块红色边框 vs 卡片背景 | `hsl(0 70% 60% / 0.4)` | 同 | ≥ 3:1 |

---

## 三、国际化 (i18n)

### 3.1 字符串本地化

- 所有用户可见字符串通过 `uiStrings.explainCard` 提供 zh / en 双值；不在组件中硬编码。
- 新增 key 在 `data-model.md` 与 `goals-duty.md` Duty 7 中列出。

### 3.2 排版

- 中文标点保留中文（如`「」`、`。`），不强制半角化。
- 错误文案避免直译："Generation failed" 对应 "生成失败"，而非 "生成失败了" 这种过于口语的形式。

### 3.3 字体回退

- 引用块中可能包含用户从 PDF/网页摘出的文本，可能含日文 / 韩文 / 表情符号 / Emoji（用户原文中的，不是 UI 元素）；浮卡 CSS 应使用默认 fallback 字体栈，**不指定 monospace 或装饰字体**。

---

## 四、深浅色模式 (Theming)

### 4.1 CSS 变量映射

```css
.explain-card {
  --explain-accent: hsl(270 60% 70%);          /* 浅色：明亮淡紫 */
  --explain-error-border: hsl(0 70% 60% / 0.4);
  --explain-error-bg: hsl(0 70% 95%);
}
.dark .explain-card {
  --explain-accent: hsl(270 35% 60%);          /* 深色：降饱和淡紫 */
  --explain-error-border: hsl(0 50% 50% / 0.5);
  --explain-error-bg: hsl(0 30% 18%);
}
```

### 4.2 阴影

- 浅色：`box-shadow: 0 12px 32px -8px rgba(0,0,0,0.12)`。
- 深色：`box-shadow: 0 12px 32px -8px rgba(0,0,0,0.5)`——黑色更重，否则深色卡片"浮不起来"。

### 4.3 黑点呼吸的颜色

- 浅色：`hsl(220 10% 25%)`（接近黑、不纯黑）。
- 深色：`hsl(220 5% 90%)`（接近白）。
- **不直接用 `--foreground`** 是因为深色模式下纯白点过于刺眼，需要轻微降低亮度。

---

## 五、响应式 (Responsive)

### 5.1 视口约束

| 视口宽度 | 行为 |
|---|---|
| ≥ 768px | 正常浮卡（默认 520×680，可拖拽缩放） |
| 480–768px | 浮卡，但默认宽度收紧到视口 80%，仍可拖拽 |
| < 480px | **本批次不处理**（Non-Duty #10）；现状是浮卡可能溢出视口，已知问题 |

### 5.2 已有的视口保护

- `boundedHeight = min(size.height, viewport.height - cardTop - 16)`——保留。
- 拖拽不脱离视口的约束由 `useDraggable` 内部限制（既有逻辑）。

---

## 六、安全性 (Security)

### 6.1 内容渲染

- `MarkdownViewer` 内部已对 markdown 内容做 sanitize（既有逻辑，本批次不动）。
- 错误块的 `error.message` 来自后端或前端常量字符串，**不接受任意用户输入**。即便如此，渲染时仍走 React 默认转义（不用 `dangerouslySetInnerHTML`）。

### 6.2 引用块的原文

- `selectedText` 是用户从 Reader 选中的文本，可能含特殊字符 / HTML 实体。
- 引用块用 `<blockquote>` + 普通 text node 渲染，React 自动转义。

---

## 七、可观测性 (Observability)

### 7.1 控制台日志

- 不增加新的 console.log；本批次不引入埋点。
- 现有 `useChatSession` 中的错误日志保留。

### 7.2 错误码透传

- 错误块在内部 DOM 上以 `data-error-code="..."` 属性暴露错误码，便于浏览器 e2e / Playwright 抓取。
- 错误码本身**不展示给用户**——除非 i18n 文案有意保留（如开发模式）。

---

## 八、可维护性 (Maintainability)

### 8.1 代码组织

- 不拆多个仅服务此卡片的展示组件；`ExplainCard` 保持单文件宿主，本地 helper 只表达渲染分支。
- `useTypewriterBuffer` 保持独立；纯逻辑 + rAF，可单测。

### 8.2 命名

- 所有新 CSS class 以 `explain-card-*` 前缀避免与既有冲突。
- CSS 变量名 `--explain-accent` 局部声明在 `.explain-card` / `.explain-card-pill` 选择器下，**不进入 `:root`**。

### 8.3 删除清单

实施后必须显式删除：

- `explain-card.tsx` 中的 `ResizeObserver`、`MutationObserver`、`updateAnchor` rAF 循环（三件套）。
- `reader.css` 第 21 节中**展开卡片**的黄色 `border-left`、`linear-gradient` 黄色渐变（替换为新样式）。
- pill 与展开卡片标题栏中的 `badge-explain` / `badge-conclude` / `badge-bee` 颜色类引用（改为"按 mode 上色的纯文字 / 小圆点"组合）。
- pill 内的 `.streaming-dot` 黄色脉冲样式（改为 `.explain-card-pill-dot` 黑点呼吸）。

实施后**保留**：

- 一个轻量 `window.addEventListener("resize", recomputeAnchor)`——仅在卡片展开期间存活，用于重算 fixed 定位的初始 `top` / `right`。
- pill 的外壳（淡边框 + 圆角），仅去掉内部 `badge-*` 黄胶囊。

### 8.4 文档同步

修改本模块代码必须同步更新：

- 若改 typewriter 节奏参数 → 改 `non-functional.md` § 1.1。
- 若新增/调整 i18n key → 改 `goals-duty.md` Duty 7 表格与 `data-model.md` § 二。
- 若调整 lastInteractionKey 哈希算法 → 改 `data-model.md` § 二。

---

## 九、暂缓 / 跟踪项

以下项不在本批次范围，但记录以便后续批次接力：

| 项 | 原因 | 建议批次 |
|---|---|---|
| 引用来源 (sources) 展示 | Non-Duty #1 | "对话记录式回溯"批次 |
| 阶段标签 (phase) 展示 | Non-Duty #6 | 同上 |
| ✕ 关闭按钮 | Non-Duty #5 | 视用户反馈再决定 |
| 拖拽位置持久化 | Non-Duty #4 | 视用户反馈 |
| 窄屏 < 480px 全屏布局 | Non-Duty #10 | 移动端响应式批次 |
| `warning` 事件 UI | Non-Duty #6 | 待后端 warning 用例明确后 |
| 错误码 → retryable 映射表 | data-model.md 暂用默认 true | 错误处理统一改造批次 |

---

## 十、自检

| 检查项 | 通过条件 |
|---|---|
| 流式节奏可感 | 用户报告"看得见字在动"，且无停顿感 |
| 黑点呼吸不闪烁 | DevTools 无 layout / paint 抖动 |
| 模式切换无硬切 | 用户报告"切换很自然" |
| 错误不污染内容 | 抓 SSE error 注入测试，content 中无错误码 |
| 删除位置追踪后无回归 | 拖拽 Main 面板大小调整，卡片始终贴右上角 |
| 深色模式视觉一致 | 浅深色模式 A/B 截图无突兀差异 |
| a11y 扫描通过 | axe-core 在卡片各态下无违规 |
| i18n 完整 | 切换 zh / en 时无英文残留或缺翻译 |
