# 前端设计系统规范 (Design System) - Academic Pure

本文档定义 Newbee Notebook 的视觉设计语言。核心理念：**清爽、学术、内容优先**。摒弃过度装饰的 "AI 风格"，打造类似 Google NotebookLM 的专业工具体验。

---

## 1. 设计原则 (Design Principles)

1.  **Content First (内容至上)**: UI 是容器，不应喧宾夺主。最大限度减少装饰性元素，让用户的注意力集中在文档和对话上。
2.  **Academic & Clean (学术清爽)**: 模拟高质量的学术阅读环境。使用冷静的色调、充足的留白和严谨的排版。
3.  **Subtle Interactions (细腻交互)**: 动画应快且难以察觉（<200ms），仅提供必要的反馈，不拖慢操作流。
4.  **Tangible (触感)**: 使用微圆角和物理感阴影，让界面元素显得稳重可靠，而非轻浮。

---

## 2. 色彩系统 (Color System)

基于 Tailwind CSS `slate` (冷灰) 和 `blue` (蓝) 色系定制。

### 2.1 主色调 (Primary) - 柔和学术蓝

不使用高饱和度的纯蓝，选择带有灰度的蓝，更耐看。

- **Brand Color**: `bg-blue-600` (Tailwind 默认的 blue-600 略微偏亮，我们视觉上向 slate 靠拢)
- **Primary Button**: `bg-slate-900` (深色按钮，不仅是蓝，更显专业) 或 `bg-blue-600`
- **Hover**: `hover:bg-blue-700`

### 2.2 中性色 (Neutrals) - 骨架

界面大面积使用的颜色。

- **Page Background**: `bg-white` (主内容区) / `bg-slate-50` (侧边栏/背景底色)
- **Surface**: `bg-white`
- **Border**: `border-slate-200` (极淡的边界)
- **Text Primary**: `text-slate-900` (正文，接近纯黑但柔和)
- **Text Secondary**: `text-slate-500` (次要信息，注释)
- **Text Muted**: `text-slate-400` (不可用状态)

### 2.3 功能色 (Functional)

用于状态反馈，保持克制。

- **Success**: `text-emerald-600` / `bg-emerald-50` (已完成)
- **Warning**: `text-amber-600` / `bg-amber-50` (已转换/处理中)
- **Error**: `text-rose-600` / `bg-rose-50` (失败)
- **Info**: `text-blue-600` / `bg-blue-50` (链接/提示)

---

## 3. 排版 (Typography)

### 3.1 字体栈 (Font Stack)

优先使用系统字体栈，保证加载速度，同时引入 Google Fonts 优化。

```css
font-family: 'Inter', 'Noto Sans SC', system-ui, -apple-system, sans-serif;
```

### 3.2 字号阶梯 (Type Scale)

- **H1**: `text-2xl font-semibold tracking-tight` (页面标题)
- **H2**: `text-xl font-medium tracking-tight` (区域标题)
- **H3**: `text-lg font-medium` (卡片标题)
- **Body**: `text-sm` (默认界面字体，14px)
- **Small**: `text-xs` (辅助信息，12px)
- **Reading**: `text-base` (长文档阅读，16px，增加行高 `leading-7`)

---

## 4. 形状与质感 (Shapes & Effects)

### 4.1 圆角 (Border Radius)

放弃大圆角 (`rounded-2xl`)，采用更严谨的微圆角。

- **Base**: `rounded-md` (6px) —— 用于按钮、输入框、卡片
- **Small**: `rounded-sm` (4px) —— 用于标签、Badge
- **Large**: `rounded-lg` (8px) —— 用于模态框 (Dialog)

### 4.2 阴影 (Shadows)

使用漫反射阴影，避免生硬的黑边。

- **Sm**: `shadow-sm` —— 卡片默认状态
- **Md**: `shadow-md` —— 悬浮状态 / 下拉菜单
- **Lg**: `shadow-lg` —— 模态框 / 浮动 ExplainCard

### 4.3 玻璃拟态 (Glassmorphism)

仅用于遮罩和浮动层，保持通透。

- **Overlay**: `bg-white/80 backdrop-blur-md border-b border-slate-200/50`

---

## 5. 组件样式 (Component Styles)

### 5.1 按钮 (Button)

- **Primary**: 深色实心，强调行动。
  `bg-slate-900 text-white hover:bg-slate-800 rounded-md shadow-sm active:scale-95 transition-all`
- **Secondary**: 白色背景，灰色边框。
  `bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 rounded-md shadow-sm`
- **Ghost**: 无背景，悬浮显色。
  `text-slate-600 hover:bg-slate-100 hover:text-slate-900 rounded-md`
- **Destructive**: 红色文本或背景。

### 5.2 卡片 (Card) -- SourceCard / NotebookCard

- **Container**: `bg-white border border-slate-200 rounded-md shadow-sm hover:shadow-md transition-shadow duration-200`
- **Header**: 简洁的标题和图标组合。
- **Interactive**: 点击时整体微动 `hover:-translate-y-0.5` (可选，保持克制)。

### 5.3 徽标 (Badge)

扁平化设计，使用背景色区分状态，避免实心强色块。

- **Default**: `bg-slate-100 text-slate-700 border border-slate-200`
- **Processing (Blue)**: `bg-blue-50 text-blue-700 border border-blue-200`
- **Converted (Amber)**: `bg-amber-50 text-amber-700 border border-amber-200`
- **Completed (Green)**: `bg-emerald-50 text-emerald-700 border border-emerald-200`

---

## 6. 动效 (Animation)

所有动效必须服务于逻辑，而非装饰。

- **Duration**: `duration-200` (标准) / `duration-300` (进场)
- **Easing**: `ease-out` (自然减速)
- **Transition**: `transition-all` (用于颜色、阴影、位置变化)

**微交互示例**:
- 按钮点击: `active:scale-95`
- 列表项悬浮: `hover:bg-slate-50`
- Skeleton 加载: `animate-pulse bg-slate-100`

---

## 7. 布局与留白 (Layout & Spacing)

采用宽松的布局，避免信息过载。

- **Padding**: 默认容器内边距 `p-4` (16px) 或 `p-6` (24px)。
- **Gap**: 列表项间距 `gap-3` 或 `gap-4`。
- **Sidebar**: 宽度固定 (e.g., `w-64`, `w-80`)，背景色略深于主内容区 (`bg-slate-50`) 以区分层级。

---

## 8. Tailwind 配置建议 (`tailwind.config.ts`)

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        // ... 其他 shadcn/ui 变量
        // 自定义学术蓝
        brand: {
           50: '#f0f9ff',
           100: '#e0f2fe',
           500: '#0ea5e9', // Sky blue
           600: '#0284c7',
           900: '#0c4a6e',
        }
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      boxShadow: {
        'glass': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
      }
    },
  },
  plugins: [require("tailwindcss-animate")],
};
export default config;
```

---

## 9. 移除 "AI 味"

- **禁止**: 全屏极光背景、大范围紫/粉渐变、发光的边框、打字机光标特效。
- **提倡**: 干净的白色背景、清晰的灰色文字、标准的系统光标、极简的加载 Spinner。
