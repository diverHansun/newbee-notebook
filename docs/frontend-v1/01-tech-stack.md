# 前端技术栈

## 1. 概述

本文档描述MediMind Agent前端的技术栈选型,参考了SurfSense、Open Notebook和RAGFlow等项目的设计。

---

## 2. 核心框架

| 类别 | 选型 | 版本 | 说明 |
|------|------|------|------|
| 框架 | Next.js | 15.x | App Router, 服务端渲染 |
| 语言 | TypeScript | 5.x | 类型安全 |
| 运行时 | React | 19.x | UI库 |

### 2.1 选择Next.js的原因

1. App Router提供更好的路由组织
2. 服务端组件减少客户端bundle
3. API Routes便于代理后端请求
4. 内置图片优化
5. 社区活跃,生态丰富

---

## 3. UI组件

| 类别 | 选型 | 说明 |
|------|------|------|
| 组件库 | shadcn/ui | 基于Radix UI,可定制 |
| 样式 | Tailwind CSS 4.x | 原子化CSS |
| 图标 | Lucide React | 轻量图标库 |
| 主题 | next-themes | 深色/浅色模式切换 |

### 3.1 shadcn/ui组件清单

项目需要的组件:

```
# 基础组件
button
input
textarea
select
checkbox
dialog
sheet (抽屉)
popover
tooltip
scroll-area
separator

# 布局组件
resizable (可调整面板)
tabs
accordion
collapsible

# 反馈组件
toast (sonner)
skeleton
progress
badge

# 数据展示
card
table
```

---

## 4. 状态管理

| 类别 | 选型 | 用途 |
|------|------|------|
| 客户端状态 | Zustand | 全局UI状态 |
| 服务端状态 | TanStack Query | 数据获取和缓存 |

### 4.1 Zustand Store划分

```typescript
// stores/
├── notebook-store.ts    // 当前notebook、文档列表
├── chat-store.ts        // 消息、会话状态
├── reader-store.ts      // 阅读器状态、选中文本
└── ui-store.ts          // 面板折叠、主题等
```

### 4.2 TanStack Query使用场景

```typescript
// 数据获取
useQuery(['notebook', notebookId], fetchNotebook)
useQuery(['documents', notebookId], fetchDocuments)
useQuery(['sessions', notebookId], fetchSessions)

// 数据变更
useMutation(createDocument)
useMutation(sendMessage)
```

---

## 5. Markdown渲染

| 类别 | 选型 | 说明 |
|------|------|------|
| 解析器 | react-markdown | React组件化渲染 |
| 扩展 | remark-gfm | GitHub风格Markdown |
| 代码高亮 | shiki | 语法高亮 |

### 5.1 自定义组件映射

```typescript
const components = {
  h1: ({ children }) => <h1 className="text-2xl font-bold mt-6 mb-4">{children}</h1>,
  h2: ({ children }) => <h2 className="text-xl font-semibold mt-5 mb-3">{children}</h2>,
  p: ({ children }) => <p className="mb-4 leading-relaxed">{children}</p>,
  ul: ({ children }) => <ul className="list-disc pl-6 mb-4">{children}</ul>,
  table: ({ children }) => (
    <div className="overflow-x-auto mb-4">
      <table className="min-w-full border">{children}</table>
    </div>
  ),
  code: ({ inline, children }) => inline
    ? <code className="bg-muted px-1 rounded">{children}</code>
    : <CodeBlock>{children}</CodeBlock>,
};
```

---

## 6. HTTP客户端

| 类别 | 选型 | 说明 |
|------|------|------|
| 请求 | fetch (内置) | 原生API |
| SSE处理 | ReadableStream | 流式响应 |

### 6.1 SSE流式响应处理

```typescript
async function streamChat(
  notebookId: string,
  message: string,
  mode: string,
  context?: SelectionContext,
  onChunk: (chunk: string) => void,
  onSources: (sources: Source[]) => void,
) {
  const response = await fetch(
    `/api/v1/chat/notebooks/${notebookId}/chat/stream`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify({
        message,
        mode,
        context,
      }),
    }
  );

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const text = decoder.decode(value);
    const lines = text.split('\n');

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        const eventType = line.slice(7);
        // 处理事件类型
      }
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        if (data.delta) onChunk(data.delta);
        if (data.sources) onSources(data.sources);
      }
    }
  }
}
```

---

## 7. 开发工具

| 类别 | 选型 | 说明 |
|------|------|------|
| 包管理 | pnpm | 快速、节省磁盘 |
| 代码检查 | ESLint | 代码规范 |
| 格式化 | Prettier | 代码格式 |
| Git Hooks | husky + lint-staged | 提交前检查 |

---

## 8. 项目初始化

### 8.1 创建项目

```bash
pnpm create next-app@latest medimind-frontend --typescript --tailwind --eslint --app --src-dir
```

### 8.2 安装依赖

```bash
# UI组件
pnpm add @radix-ui/react-dialog @radix-ui/react-popover @radix-ui/react-tabs
pnpm add @radix-ui/react-scroll-area @radix-ui/react-tooltip
pnpm add class-variance-authority clsx tailwind-merge
pnpm add lucide-react
pnpm add next-themes
pnpm add sonner

# 状态管理
pnpm add zustand
pnpm add @tanstack/react-query

# Markdown
pnpm add react-markdown remark-gfm
pnpm add shiki

# 开发依赖
pnpm add -D @types/node @types/react
```

### 8.3 shadcn/ui初始化

```bash
pnpm dlx shadcn@latest init

# 添加组件
pnpm dlx shadcn@latest add button input textarea
pnpm dlx shadcn@latest add dialog sheet popover
pnpm dlx shadcn@latest add tabs card badge
pnpm dlx shadcn@latest add scroll-area separator
pnpm dlx shadcn@latest add resizable
```

---

## 9. 目录结构

```
src/
├── app/                      # Next.js App Router
│   ├── layout.tsx           # 根布局
│   ├── page.tsx             # 首页
│   ├── notebooks/
│   │   └── [id]/
│   │       └── page.tsx     # Notebook页面
│   └── api/                 # API Routes (代理)
├── components/
│   ├── ui/                  # shadcn/ui组件
│   ├── layout/              # 布局组件
│   │   ├── app-shell.tsx
│   │   ├── sidebar.tsx
│   │   └── header.tsx
│   ├── sources/             # 文档相关
│   │   ├── source-list.tsx
│   │   ├── source-card.tsx
│   │   └── add-source-dialog.tsx
│   ├── reader/              # 阅读器
│   │   ├── document-reader.tsx
│   │   ├── markdown-viewer.tsx
│   │   └── selection-menu.tsx
│   ├── chat/                # 聊天
│   │   ├── chat-panel.tsx
│   │   ├── message-list.tsx
│   │   ├── message-item.tsx
│   │   ├── chat-input.tsx
│   │   └── source-card.tsx
│   └── studio/              # Studio区域(预留)
├── lib/
│   ├── api/                 # API调用
│   │   ├── documents.ts
│   │   ├── notebooks.ts
│   │   ├── chat.ts
│   │   └── sessions.ts
│   ├── hooks/               # 自定义Hooks
│   │   ├── use-text-selection.ts
│   │   ├── use-chat-stream.ts
│   │   └── use-document-content.ts
│   └── utils/               # 工具函数
├── stores/                  # Zustand stores
│   ├── notebook-store.ts
│   ├── chat-store.ts
│   ├── reader-store.ts
│   └── ui-store.ts
├── types/                   # TypeScript类型
│   ├── document.ts
│   ├── notebook.ts
│   ├── chat.ts
│   └── api.ts
└── styles/
    └── globals.css          # 全局样式
```

---

## 10. 配置文件

### 10.1 next.config.js

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'http://localhost:8000/api/v1/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
```

### 10.2 tailwind.config.js

```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ['class'],
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // shadcn/ui颜色变量
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
};
```
