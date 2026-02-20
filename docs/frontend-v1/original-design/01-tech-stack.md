# 前端技术栈

## 1. 概述

本文档描述 Newbee Notebook 前端的技术栈选型。详细的模块设计见 `plan-1/` 目录下的各模块文档。

---

## 2. 核心框架

| 类别 | 选型 | 版本 | 说明 |
|------|------|------|------|
| 框架 | Next.js | 15.x | App Router, 服务端渲染 |
| 语言 | TypeScript | 5.x | 类型安全 |
| 运行时 | React | 19.x | UI 库 |

### 2.1 选择 Next.js 的原因

1. App Router 提供更好的路由组织
2. 服务端组件减少客户端 bundle
3. API Routes 便于代理后端请求（rewrites 转发 `/api/v1/*`）
4. 社区活跃，生态丰富

---

## 3. UI 组件

| 类别 | 选型 | 说明 |
|------|------|------|
| 组件库 | shadcn/ui | 基于 Radix UI，可定制 |
| 样式 | Tailwind CSS 4.x | 原子化 CSS |
| 图标 | Lucide React | 轻量图标库 |
| 主题 | next-themes | light/dark 模式切换 |

### 3.1 shadcn/ui 组件清单

项目需要的组件：

```
# 基础组件
button, input, textarea, select, checkbox
dialog, sheet（抽屉）, popover, tooltip
scroll-area, separator

# 布局组件
resizable（可调整面板）, tabs, accordion, collapsible

# 反馈组件
toast (sonner), skeleton, progress, badge

# 数据展示
card, table, dropdown-menu
```

---

## 4. 状态管理

| 类别 | 选型 | 用途 |
|------|------|------|
| 客户端状态 | Zustand | 全局 UI 状态 |
| 服务端状态 | TanStack Query | 数据获取和缓存 |

### 4.1 Zustand Store 划分

| Store | 存储内容 | 持久化 |
|-------|----------|--------|
| ui-store | 面板折叠状态、当前视图模式、侧边栏状态 | localStorage |
| reader-store | 当前查看的文档 ID、文本选择上下文、选择菜单位置 | 不持久化 |
| chat-store | 当前会话 ID、消息列表、流式状态标记、当前 mode、explain/conclude 卡片内容 | 不持久化 |

设计原则：Zustand 只存储客户端状态，不缓存服务端数据（服务端数据由 TanStack Query 管理）。

### 4.2 TanStack Query 使用场景

```typescript
// 数据获取
useQuery({ queryKey: ['notebook', notebookId], queryFn: fetchNotebook })
useQuery({ queryKey: ['notebook-documents', notebookId], queryFn: fetchDocuments })
useQuery({ queryKey: ['sessions', notebookId], queryFn: fetchSessions })
useQuery({ queryKey: ['document-content', documentId], queryFn: fetchDocumentContent })

// 数据变更
useMutation({ mutationFn: createNotebook, onSuccess: () => invalidate(['notebooks']) })
useMutation({ mutationFn: uploadDocument, onSuccess: () => invalidate(['notebook-documents', notebookId]) })
```

---

## 5. Markdown 渲染

| 类别 | 选型 | 说明 |
|------|------|------|
| 渲染管线 | unified / remark / rehype | 可扩展的 AST 处理管线 |
| 输出层 | rehype-react | 将 HTML AST 转为 React 元素 |
| 代码高亮 | highlight.js (rehype-highlight) | 语法高亮，按需加载语言包 |
| 数学公式 | KaTeX (rehype-katex + remark-math) | 公式渲染 |
| GFM 支持 | remark-gfm | 表格、任务列表、删除线等 |

### 5.1 渲染管线

采用 unified 生态的管线架构，替代 react-markdown 的单组件方案。管线处理流程：

```
Markdown 文本
  | remark-parse        -- Markdown -> mdast
  | remark-gfm          -- GFM 扩展语法
  | remark-math         -- 数学公式语法
  | remark-cjk-friendly -- 中日韩排版优化
  | remark-rehype       -- mdast -> hast
  | rehype-slug         -- 标题添加 id 锚点
  | rehype-highlight    -- 代码块语法高亮
  | rehype-katex        -- 数学公式渲染
  | rehype-react        -- hast -> React 元素
  v
React 组件树
```

无需自定义插件。后端在文档处理保存阶段（`save_markdown()` 函数）已将 MinerU 输出的相对图片路径转换为 API 绝对路径（`/api/v1/documents/{id}/assets/images/{hash}.jpg`），前端管线无需做路径转换。详见 `plan-1/01-markdown-viewer/` 文档。

### 5.2 代码高亮策略

使用 highlight.js 通过 rehype-highlight 集成。捆绑约 40 种常用语言（JavaScript、TypeScript、Python、Java、C/C++、Go、Rust、SQL、Shell、JSON、YAML、HTML、CSS 等），不使用全量包以控制 bundle 体积。

### 5.3 内容样式

Markdown 渲染区域的排版风格借鉴 VS Code / Cursor 内置的 Markdown Preview 样式，通过独立的 CSS 文件（`markdown-content.css`）实现，不使用 Tailwind Typography 插件。样式基于 CSS 变量响应 light/dark 主题切换。

---

## 6. HTTP 客户端

| 类别 | 选型 | 说明 |
|------|------|------|
| 请求 | fetch（内置） | 原生 API，不引入 axios |
| SSE 处理 | ReadableStream | 流式响应解析 |

### 6.1 SSE 流式响应处理

后端流式端点为 POST 请求，不支持 EventSource API（EventSource 仅支持 GET）。使用原生 `fetch` + `ReadableStream` + `AbortController` 实现。

SSE 事件格式：每个事件为 `data: {JSON}\n\n`，JSON 中通过 `type` 字段区分事件类型。

```
事件类型          | 数据字段                                  | 说明
-----------------|------------------------------------------|------------------
start            | { type: "start", message_id: number }    | 流开始，返回消息 ID
content          | { type: "content", delta: string }       | 增量文本内容
sources          | { type: "sources", sources: Source[] }   | 引用来源列表
done             | { type: "done" }                         | 流正常结束
error            | { type: "error", error_code, message }   | 错误信息
heartbeat        | { type: "heartbeat" }                    | 心跳（约 15 秒间隔）
```

SSE 解析的核心逻辑：维护文本缓冲区，每次从 ReadableStream 读取数据时追加到缓冲区，按 `\n\n` 分割完整事件，提取 `data:` 行内容并解析为 JSON。该解析逻辑封装在 `lib/utils/sse-parser.ts` 中，不绑定聊天业务逻辑，可复用。

### 6.2 流式取消

客户端通过 `AbortController.abort()` 关闭 SSE 连接，同时调用 `POST /chat/stream/{message_id}/cancel` 通知后端停止生成。

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
pnpm create next-app@latest newbee-frontend --typescript --tailwind --eslint --app --src-dir
```

### 8.2 安装依赖

```bash
# UI 组件
pnpm add @radix-ui/react-dialog @radix-ui/react-popover @radix-ui/react-tabs
pnpm add @radix-ui/react-scroll-area @radix-ui/react-tooltip
pnpm add class-variance-authority clsx tailwind-merge
pnpm add lucide-react
pnpm add next-themes
pnpm add sonner

# 状态管理
pnpm add zustand
pnpm add @tanstack/react-query

# Markdown 渲染管线
pnpm add unified remark-parse remark-gfm remark-math remark-rehype
pnpm add rehype-react rehype-highlight rehype-katex rehype-slug
pnpm add remark-cjk-friendly
pnpm add katex

# 开发依赖
pnpm add -D @types/node @types/react @types/hast
```

### 8.3 shadcn/ui 初始化

```bash
pnpm dlx shadcn@latest init

# 添加组件
pnpm dlx shadcn@latest add button input textarea
pnpm dlx shadcn@latest add dialog sheet popover tooltip
pnpm dlx shadcn@latest add tabs card badge
pnpm dlx shadcn@latest add scroll-area separator
pnpm dlx shadcn@latest add resizable dropdown-menu
pnpm dlx shadcn@latest add skeleton progress
```

---

## 9. 目录结构

```
src/
├── app/                          # Next.js App Router
│   ├── layout.tsx               # 根布局（ThemeProvider, QueryProvider）
│   ├── page.tsx                 # 首页（重定向到 /notebooks）
│   ├── notebooks/
│   │   ├── page.tsx             # Notebook 列表
│   │   └── [id]/
│   │       ├── layout.tsx       # 详情页布局（面板状态管理）
│   │       └── page.tsx         # Notebook 详情（三栏布局）
│   └── library/
│       └── page.tsx             # Library 管理
├── components/
│   ├── ui/                      # shadcn/ui 组件
│   ├── layout/                  # 布局组件
│   │   ├── app-shell.tsx
│   │   └── header.tsx
│   ├── sources/                 # 文档源面板
│   │   ├── source-list.tsx
│   │   ├── source-card.tsx
│   │   └── add-source-dialog.tsx
│   ├── reader/                  # Markdown 阅读器
│   │   ├── MarkdownViewer.tsx   # 渲染组件（调用管线输出 React 树）
│   │   ├── SelectionMenu.tsx    # 文本选中浮动菜单
│   │   ├── markdown-pipeline.ts # unified 管线配置
│   │   └── styles/
│   │       └── markdown-content.css  # Markdown 内容区排版样式
│   ├── chat/                    # 聊天系统
│   │   ├── ChatPanel.tsx        # 主聊天面板（chat/ask 模式）
│   │   ├── ChatInput.tsx        # 消息输入框
│   │   ├── MessageItem.tsx      # 单条消息渲染
│   │   ├── SourcesCard.tsx      # 来源引用卡片
│   │   └── ExplainCard.tsx      # explain/conclude 浮动卡片
│   └── studio/                  # Studio 区域（待定）
├── lib/
│   ├── api/                     # API 调用
│   │   ├── client.ts            # fetch 封装、错误处理
│   │   ├── documents.ts
│   │   ├── notebooks.ts
│   │   ├── chat.ts
│   │   ├── sessions.ts
│   │   ├── library.ts
│   │   └── types.ts             # 请求/响应类型定义
│   ├── hooks/                   # 自定义 Hooks
│   │   ├── useTextSelection.ts  # 文本选中检测 + 位置计算
│   │   ├── useChatStream.ts     # SSE 流式通信
│   │   └── useChatSession.ts    # 会话管理
│   └── utils/                   # 工具函数
│       └── sse-parser.ts        # SSE 流解析（通用）
├── stores/                      # Zustand stores
│   ├── ui-store.ts
│   ├── chat-store.ts
│   └── reader-store.ts
├── types/                       # TypeScript 类型
│   ├── document.ts
│   ├── notebook.ts
│   ├── chat.ts
│   └── api.ts
└── styles/
    ├── globals.css              # 全局样式
    └── markdown-content.css     # Markdown 渲染区域样式
```

---

## 10. 配置文件

### 10.1 next.config.ts

```typescript
import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'http://localhost:8000/api/v1/:path*',
      },
    ];
  },
};

export default nextConfig;
```

### 10.2 主题配置

仅实现 light/dark 两套主题，通过 CSS 变量定义颜色体系，由 next-themes 管理切换。shadcn/ui 内置的 CSS 变量方案天然支持双主题，无需额外配置。后续如需扩展更多主题预设，可在 CSS 变量层扩展。
