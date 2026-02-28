# P4 删除按钮样式统一与 Dark Mode 适配

## 问题描述

项目中所有"删除"类操作的按钮在视觉风格上存在不一致，尤其在 Dark Mode 下问题突出。
具体表现为三个方面：色彩体系混用、Dark Mode 色值不适配、样式实现方式分散。

## 问题定位

### 1. 确认弹窗中红色与琥珀色混用

`ConfirmDialog` 组件支持两种 `variant`：

- `danger` -- 红色实心确认按钮（`--destructive` 背景）
- `warning` -- 琥珀色实心确认按钮（`--bee-yellow-light` 背景 + 硬编码 `#92400E` 文字）

实际使用情况：

| 场景 | 所在文件 | variant | 确认按钮颜色 |
|------|----------|---------|-------------|
| Library 软删除 | `app/library/page.tsx` | `warning` | 琥珀色 |
| Library 彻底删除 | `app/library/page.tsx` | `danger` | 红色 |
| Library 批量删除 | `app/library/page.tsx` | `danger` | 红色 |
| Notebook 删除 | `app/notebooks/page.tsx` | `danger` | 红色 |
| Chat 会话删除 | `components/chat/chat-panel.tsx` | `danger` | 红色 |
| Source 移除文档 | `components/sources/source-list.tsx` | `warning` | 琥珀色 |

同一页面（Library）中，"确认删除"是琥珀色、"确认彻底删除"是红色，
用户在连续操作时看到两种截然不同的色彩，造成认知混乱。

### 2. Dark Mode 下 `--destructive` 色值过暗

`globals.css` 中的 CSS 变量定义：

```css
/* Light */
--destructive: 0 84% 60%;            /* rose-500, 视觉清晰 */
--destructive-foreground: 0 0% 100%;  /* 纯白 */

/* Dark -- 当前值 */
--destructive: 0 63% 31%;            /* 亮度仅 31%, 极暗 */
--destructive-foreground: 210 40% 98%; /* 蓝灰白, 非纯白 */
```

Dark Mode 下 `--destructive` 亮度仅 31%，而 card 背景为 `217 33% 17%`（亮度 17%）。
两者亮度差仅 14 个百分点，导致红色实心按钮几乎融入深色背景，视觉辨识度极低。

### 3. `btn-danger-ghost` 的 Dark Mode 硬编码

`buttons.css` 中 Dark Mode 下的 ghost 删除按钮使用了硬编码色值：

```css
.dark .btn-danger-ghost {
  color: hsl(351 89% 76%);           /* 粉红色, 非变量 */
}
.dark .btn-danger-ghost:hover {
  background: hsl(351 89% 76% / 0.12);
  border-color: hsl(351 89% 76% / 0.26);
  color: hsl(351 95% 84%);           /* 更亮的粉红 */
}
```

这些硬编码值与 `--destructive` 变量完全脱节，无法随主题变量统一调整。

### 4. 确认按钮用 inline style 而非 CSS class

`confirm-dialog.tsx` 中确认按钮的样式通过 JS 对象内联注入：

```tsx
const confirmStyle =
  variant === "warning"
    ? { background: "hsl(var(--bee-yellow-light))", color: "#92400E", ... }
    : { background: "hsl(var(--destructive))", ... };

<button style={confirmStyle}>确认删除</button>
```

这种方式无法被 `.dark` 选择器覆盖，Dark Mode 下 warning 的 `#92400E` 始终是深褐色，
在低亮度黄色背景上对比度不足。

## 修改方案

### 设计原则

1. 所有删除操作统一使用红色系视觉语言，不再混用琥珀色
2. 通过按钮"填充强度"区分操作严重性：outline（可恢复）vs solid（不可逆）
3. 样式通过 CSS class + 变量管控，消除 inline style 和硬编码色值
4. Dark Mode 下保证充足的对比度和可读性

### 改动清单

#### 改动 1：调整 Dark Mode 的 `--destructive` 变量

文件：`app/globals.css`

| 变量 | 修改前 | 修改后 |
|------|--------|--------|
| `--destructive` | `0 63% 31%` (亮度31%) | `0 72% 51%` (亮度51%) |
| `--destructive-foreground` | `210 40% 98%` (蓝灰) | `0 0% 100%` (纯白) |

新增供 Dark Mode ghost 按钮使用的语义化变量：

| 新变量 | 值 | 用途 |
|--------|------|------|
| `--destructive-text` | `0 90% 72%` | Dark ghost 按钮文字色 |
| `--destructive-text-hover` | `0 90% 80%` | Dark ghost 按钮 hover 文字色 |

#### 改动 2：新增 `btn-destructive-outline` CSS class

文件：`styles/buttons.css`

新增 outline 风格的删除按钮，用于确认弹窗中"可恢复删除"的确认按钮：

```css
.btn-destructive-outline {
  background: transparent;
  color: hsl(var(--destructive));
  border-color: hsl(var(--destructive));
}
.btn-destructive-outline:hover {
  background: hsl(var(--destructive) / 0.08);
}
.dark .btn-destructive-outline {
  color: hsl(var(--destructive-text));
  border-color: hsl(var(--destructive-text) / 0.5);
}
.dark .btn-destructive-outline:hover {
  background: hsl(var(--destructive-text) / 0.1);
  color: hsl(var(--destructive-text-hover));
}
```

#### 改动 3：`btn-danger-ghost` 去除硬编码

文件：`styles/buttons.css`

将 `.dark .btn-danger-ghost` 的硬编码 `hsl(351 89% 76%)` 更换为 `--destructive-text` 变量引用。

#### 改动 4：重构 `ConfirmDialog` 确认按钮样式

文件：`components/ui/confirm-dialog.tsx`

- 删除 `confirmStyle` inline style 对象
- 改用 CSS class：`variant="danger"` 使用 `btn-destructive`，`variant="warning"` 使用 `btn-destructive-outline`
- `warning` 语义从"琥珀色"变为"红色 outline"，表示"可恢复的谨慎操作"

修改前：
```tsx
const confirmStyle =
  variant === "warning"
    ? { background: "hsl(var(--bee-yellow-light))", color: "#92400E", borderColor: "..." }
    : { background: "hsl(var(--destructive))", color: "...", borderColor: "..." };

<button className="btn" style={confirmStyle}>确认删除</button>
```

修改后：
```tsx
const confirmBtnClass =
  variant === "warning" ? "btn btn-destructive-outline" : "btn btn-destructive";

<button className={confirmBtnClass}>确认删除</button>
```

#### 改动 5：统一 `btn-destructive` 的 Dark Mode 表现

文件：`styles/buttons.css`

为 `.btn-destructive` 补充 Dark Mode 样式，确保足够的对比度：

```css
.dark .btn-destructive {
  box-shadow: 0 0 0 1px hsl(0 72% 51% / 0.3);
}
```

### 修改前后对比

#### Light Mode

| 元素 | 修改前 | 修改后 |
|------|--------|--------|
| 触发按钮（删除/彻底删除/移除） | 红色 ghost 文字 | 不变 |
| 确认删除（软删除/移除） | 琥珀色实心 | 红色 outline（边框+文字） |
| 确认彻底删除 | 红色实心 | 不变 |

#### Dark Mode

| 元素 | 修改前 | 修改后 |
|------|--------|--------|
| 触发按钮 | 硬编码粉红色 | 统一引用 `--destructive-text` 变量 |
| 确认删除（软删除/移除） | 暗黄背景+深褐文字（几乎不可读） | 红色 outline，文字/边框清晰 |
| 确认彻底删除 | 极暗红色背景（融入卡片背景） | 亮度提升至 51%，醒目红色实心 |

### 涉及文件

| 文件 | 改动类型 |
|------|----------|
| `app/globals.css` | 调整 CSS 变量 |
| `styles/buttons.css` | 新增 class + 改写 dark 覆盖 |
| `components/ui/confirm-dialog.tsx` | 重构确认按钮样式逻辑 |
