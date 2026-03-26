# 进度指示器：样式规格

## 设计原则

- 与现有 ThinkingIndicator 保持视觉语言一致（bee-yellow/amber 配色、8px 圆角、12px 字号）
- 复用现有动画关键帧（`thinking-spin`、`thinking-shimmer`、`thinking-fade-out`）
- 所有动画使用 GPU 加速属性（`transform`、`opacity`），不触发布局重排
- 新增样式以 `.tool-steps-` 为前缀，与现有 `.thinking-indicator-` 命名空间隔离

---

## 与现有样式的关系

### 可复用的现有资源

| 资源 | 来源文件 | 用途 |
|------|----------|------|
| `thinking-spin` 关键帧 | `animations.css` | 进行中步骤的旋转圆环动画 |
| `thinking-shimmer` 关键帧 | `animations.css` | 底部进度条闪烁效果 |
| `thinking-fade-out` 关键帧 | `animations.css` | 步骤列表退出动画（预留） |
| `--bee-yellow` / `--bee-amber` CSS 变量 | `globals.css` | 品牌配色 |
| `--border` / `--muted` / `--muted-foreground` 变量 | `globals.css` | 容器和文本颜色 |

### 不修改的现有样式

`.thinking-indicator` 及其子类全部保留不变，仍然用于无工具调用场景。

---

## 新增 CSS 类定义

以下样式追加到 `frontend/src/styles/thinking-indicator.css` 文件末尾：

```css
/* ================================================================
   22b. Tool Steps Indicator
   ================================================================ */

.tool-steps-indicator {
  max-width: 280px;
  border: 1px solid hsl(var(--border));
  border-radius: 8px;
  background: hsl(var(--muted) / 0.5);
  padding: 10px 14px;
}

.tool-steps-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* ---- 单个步骤行 ---- */

.tool-step {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 20px;
}

.tool-step-label {
  font-size: 12px;
  line-height: 1.4;
  color: hsl(var(--muted-foreground));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ---- 状态图标 ---- */

.tool-step-icon {
  position: relative;
  width: 14px;
  height: 14px;
  flex: 0 0 14px;
  border-radius: 50%;
}

/* 进行中：旋转圆环（与 ThinkingIndicator 同款，缩小尺寸） */
.tool-step--running .tool-step-icon {
  background: conic-gradient(
    hsl(var(--bee-yellow)),
    hsl(var(--bee-amber)),
    hsl(var(--bee-yellow))
  );
  animation: thinking-spin 1s linear infinite;
}

.tool-step--running .tool-step-icon::after {
  content: "";
  position: absolute;
  inset: 2px;
  border-radius: 50%;
  background: hsl(var(--muted) / 0.5);
}

/* 已完成：静态对勾 */
.tool-step--done .tool-step-icon {
  background: hsl(var(--bee-amber) / 0.2);
}

.tool-step--done .tool-step-icon::after {
  content: "";
  position: absolute;
  top: 3px;
  left: 3px;
  width: 5px;
  height: 8px;
  border: solid hsl(var(--bee-amber));
  border-width: 0 1.5px 1.5px 0;
  transform: rotate(40deg);
}

.tool-step--done .tool-step-label {
  color: hsl(var(--muted-foreground) / 0.6);
}

/* 错误：红色叉号 */
.tool-step--error .tool-step-icon {
  background: hsl(0 70% 50% / 0.2);
}

.tool-step--error .tool-step-icon::before,
.tool-step--error .tool-step-icon::after {
  content: "";
  position: absolute;
  top: 50%;
  left: 50%;
  width: 8px;
  height: 1.5px;
  background: hsl(0 70% 50%);
  border-radius: 1px;
}

.tool-step--error .tool-step-icon::before {
  transform: translate(-50%, -50%) rotate(45deg);
}

.tool-step--error .tool-step-icon::after {
  transform: translate(-50%, -50%) rotate(-45deg);
}

.tool-step--error .tool-step-label {
  color: hsl(0 70% 50% / 0.8);
}

/* ---- 底部进度条（复用 shimmer 动画） ---- */

.tool-steps-progress {
  position: relative;
  margin-top: 8px;
  height: 2px;
  width: 100%;
  border-radius: 999px;
  background: hsl(var(--border));
  overflow: hidden;
}

.tool-steps-progress-bar {
  position: absolute;
  inset: 0 auto 0 0;
  width: 40%;
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    transparent 0%,
    hsl(var(--bee-yellow)) 40%,
    hsl(var(--bee-amber)) 60%,
    transparent 100%
  );
  animation: thinking-shimmer 1.2s linear infinite;
}

/* ---- 退出动画（预留，方案 B 时启用） ---- */

.tool-steps-indicator--exiting {
  animation: thinking-fade-out 0.4s ease-out forwards;
  pointer-events: none;
}
```

---

## 视觉参考

### 容器对比

| 属性 | ThinkingIndicator (现有) | ToolStepsIndicator (新增) |
|------|--------------------------|---------------------------|
| max-width | 240px | 280px |
| padding | 10px 14px | 10px 14px |
| border-radius | 8px | 8px |
| background | `hsl(var(--muted) / 0.5)` | `hsl(var(--muted) / 0.5)` |
| border | `1px solid hsl(var(--border))` | `1px solid hsl(var(--border))` |

差异仅在于 max-width 从 240px 增加到 280px，以适配更长的步骤标签。

### 图标尺寸对比

| 属性 | ThinkingIndicator ring | ToolStep icon |
|------|------------------------|---------------|
| 尺寸 | 16x16px | 14x14px |
| 内圈 inset | 2px | 2px |

步骤图标略小于 ThinkingIndicator 的圆环，因为步骤列表是紧凑布局。

### 状态视觉映射

```
running:  [旋转圆环]  蜜蜂黄/琥珀色渐变，1s 旋转周期
done:     [静态对勾]  琥珀色对勾，20% 透明度背景，标签颜色降低至 60%
error:    [静态叉号]  红色叉号，20% 透明度背景，标签颜色变为红色 80%
```

---

## 动画性能说明

所有动画仅使用 `transform` 和 `opacity` 属性：

- `thinking-spin`: `transform: rotate()` — 仅合成层操作
- `thinking-shimmer`: `transform: translateX()` — 仅合成层操作
- `thinking-fade-out`: `opacity` + `transform: translateY()` — 仅合成层操作

不触发布局（layout）或绘制（paint），确保 60fps 流畅渲染。

多个旋转图标同时存在时（多步骤同时 running），每个圆环独立在合成层上运行。实际场景中同时 running 的步骤通常为 1-2 个，无性能顾虑。

---

## 主题适配

所有颜色均通过 CSS 变量引用，自动适配亮色/暗色主题：

- `--bee-yellow` / `--bee-amber`: 品牌色，两套主题下均有定义
- `--border`: 边框色
- `--muted` / `--muted-foreground`: 背景和文本色
- `--card`: 圆环内圈背景色（ThinkingIndicator 使用）

ToolStepsIndicator 的圆环内圈使用 `hsl(var(--muted) / 0.5)` 而非 `hsl(var(--card))`，因为容器本身背景为 muted，内圈应与容器融合。
