# P3: UI 组件圆角与输入区重设计

## 问题描述

1. 全局 `--radius` 为 6px，按钮实际 `border-radius` 仅 4px（`calc(var(--radius) - 2px)`），视觉上过于方正生硬
2. Chat/Ask 模式切换使用原生 `<select>` 下拉框，与整体 UI 风格不协调
3. 发送按钮为矩形文字按钮，尺寸偏大，与 textarea 的搭配缺乏设计感
4. 各类按钮缺乏视觉层次，交互反馈单一

## 当前实现

### 全局圆角（globals.css）

```css
--radius: 0.375rem;                          /* 6px */
.btn    { border-radius: calc(var(--radius) - 2px); }  /* 4px */
.badge  { border-radius: calc(var(--radius) - 4px); }  /* 2px */
.card   { border-radius: var(--radius); }               /* 6px */
```

### ChatInput 组件（chat-input.tsx）

- `<select>` 原生下拉框，宽度 90px
- `<textarea>` 独立边框
- `<button>` 文字按钮："发送" / "取消"
- 三者以 `flex` + `gap: 8px` 平铺排列，无统一容器

## 设计方案

### 1. 全局圆角系统升级

```css
:root {
  --radius: 0.5rem;  /* 6px -> 8px */
}

.btn {
  border-radius: var(--radius);  /* 8px，不再减 2px */
}

.badge {
  border-radius: 999px;  /* pill 形状 */
}

.card {
  border-radius: calc(var(--radius) + 2px);  /* 10px */
}

.select,
.textarea {
  border-radius: var(--radius);  /* 8px */
}
```

此调整影响全局所有使用这些类的元素，无需逐个修改组件。

### 2. SegmentedControl 组件

替换原生 `<select>`，实现自定义分段控件。

#### 视觉规格

```
  ┌──────────────────┐
  │ [Chat]    Ask    │     外壳：pill 形（border-radius: 999px）
  └──────────────────┘     高度：32px
                           背景：hsl(var(--muted))
```

- 外壳：`border-radius: 999px`，`background: hsl(var(--muted))`，`padding: 3px`
- 选项：`padding: 4px 12px`，`font-size: 12px`，`font-weight: 500`
- 选中项：`background: hsl(var(--card))`，`border-radius: 999px`，`box-shadow: 0 1px 2px rgba(0,0,0,0.08)`
- 切换动画：选中背景使用 `transition: all 200ms ease-out` 滑动
- 禁用态（streaming 中）：`opacity: 0.5`，`pointer-events: none`

#### 组件接口

```typescript
type SegmentedControlProps = {
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  disabled?: boolean;
};
```

文件位置：`frontend/src/components/ui/segmented-control.tsx`

### 3. 发送按钮改为圆形图标按钮

#### 视觉规格

```
  默认态（无输入）：灰色圆形 ○
  可发送态：        填充色圆形 ● 内含向上箭头
  流式中：          红色圆形 ● 内含停止图标
```

- 尺寸：36x36px，`border-radius: 50%`
- 默认态：`background: hsl(var(--muted))`，`color: hsl(var(--muted-foreground))`
- 可发送态：`background: hsl(var(--primary))`，`color: hsl(var(--primary-foreground))`
- 取消态：`background: hsl(var(--destructive))`，`color: white`
- 图标：使用 CSS 或 SVG 绘制，不引入图标库
  - 发送：向上箭头（参考 ChatGPT/Claude 的发送图标风格）
  - 停止：方形停止符号

#### 发送图标 SVG

```svg
<!-- 向上箭头 -->
<svg width="16" height="16" viewBox="0 0 16 16" fill="none">
  <path d="M8 14V3M8 3L3 8M8 3L13 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>

<!-- 停止 -->
<svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
  <rect x="2" y="2" width="10" height="10" rx="1.5"/>
</svg>
```

### 4. 输入区整体布局重设计

#### 结构

```
┌─ chat-input-container ─────────────────────────────────┐
│                                                        │
│  ┌─ textarea ────────────────────────────────────┐     │
│  │ 输入消息...                                    │     │
│  └───────────────────────────────────────────────┘     │
│                                                        │
│  [Chat|Ask]                                    (●)     │
│  segmented-control                           send-btn  │
│                                                        │
└────────────────────────────────────────────────────────┘
```

- 外层容器（`.chat-input-container`）：
  - `border: 1px solid hsl(var(--border))`
  - `border-radius: 12px`
  - `background: hsl(var(--card))`
  - `padding: 8px 12px`
  - `box-shadow: 0 -1px 4px rgba(0,0,0,0.04)`（轻微上投影）

- textarea：
  - 去除独立边框（`border: none`）
  - 去除 focus 时的 ring（`box-shadow: none`）
  - `background: transparent`
  - 宽度 100%（不再与其他元素同行）

- 底部栏：
  - `display: flex`，`justify-content: space-between`，`align-items: center`
  - 左侧：SegmentedControl + RAG 不可用提示（如有）
  - 右侧：圆形发送/取消按钮

#### 布局变化对比

```
当前：  [Select] [Textarea] [发送按钮]    ← 三列横排

目标：  ┌───────────────────────────┐
        │ Textarea                  │    ← textarea 独占一行
        │                           │
        │ [Chat|Ask]           (●)  │    ← 底部工具栏
        └───────────────────────────┘
```

这种布局与主流聊天产品（ChatGPT、Claude）对齐，textarea 获得最大输入空间。

> **P5 扩展**：P5 会在此布局基础上新增 source chips 行（textarea 上方）和文档图标按鈕（SegmentedControl 右侧），详见 [P5 文档](P5-source-selector.md)。

### 5. 消息气泡微调

配合全局圆角升级，消息气泡也做微调：

- AI 消息气泡：左侧添加 2px 宽的竖线（`border-left: 2px solid hsl(var(--bee-yellow) / 0.6)`），增强视觉区分
- `max-width` 从 80% 调整为 85%
- `border-radius` 跟随 `.card` 的新值（10px）

## 涉及文件

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/app/globals.css` | --radius 升级，按钮/badge/card 圆角调整，输入区样式 |
| `frontend/src/components/chat/chat-input.tsx` | 布局重写，移除 select，接入 SegmentedControl |
| `frontend/src/components/ui/segmented-control.tsx` | 新增组件 |
| `frontend/src/components/chat/message-item.tsx` | 消息气泡左侧竖线，max-width 调整 |

## 验证标准

- 全局按钮、badge、card 圆角视觉统一，不再有 4px 方块感
- Chat/Ask 切换为分段控件，滑动动画流畅
- 发送按钮为圆形，无输入时灰色，有输入时高亮，streaming 时变红色停止
- 输入区为统一容器包裹，textarea 独占一行，底部栏左右分布
- AI 消息气泡有左侧 accent 竖线，与用户消息视觉区分明确
- 所有交互状态（hover、active、disabled、focus）表现正确
