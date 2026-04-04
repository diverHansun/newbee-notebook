# Frontend 启动指南

## 环境要求

| 工具 | 版本要求 |
|------|----------|
| Node.js | >= 18.x |
| pnpm | >= 10.x |

pnpm 安装方式：

```bash
npm install -g pnpm
```

---

## 开发环境启动

### 1. 安装依赖

在 `frontend/` 目录下执行：

```bash
pnpm install
```

### 2. 启动开发服务器

```bash
pnpm dev
```

启动成功后，终端会输出：

```
Local:   http://localhost:3000
Network: http://0.0.0.0:3000
```

在浏览器中打开 `http://localhost:3000`，会自动跳转到 `/notebooks` 页面。

### 3. 配置后端地址（可选）

前端通过 Next.js `rewrites` 将 `/api/v1/*` 的请求代理到后端。默认目标为 `http://localhost:8000`。

如需修改，在 `frontend/` 目录下创建 `.env.local` 文件：

```bash
# frontend/.env.local
INTERNAL_API_URL=http://localhost:8000
```

无需重启开发服务器，修改 `.env.local` 后执行 `pnpm dev` 重新启动即可生效。

如果你采用开发者常用的 host-debug 链路，请保持：
- Docker 只启动基础设施与 worker（不要同时启动 Docker 版 `api` / `frontend`）
- 宿主机运行 `python main.py --reload --port 8000`
- 前端继续用 `pnpm dev`

---

## 生产构建

### 构建

```bash
pnpm build
```

构建产物输出到 `.next/` 目录。构建过程会同时执行类型检查和 ESLint 检查，出现错误时构建会中止。

### 启动生产服务

```bash
pnpm start
```

默认监听 `http://localhost:3000`。

---

## 其他脚本

| 命令 | 说明 |
|------|------|
| `pnpm dev` | 启动开发服务器，支持热更新 |
| `pnpm build` | 生产构建（含类型检查 + Lint） |
| `pnpm start` | 以生产模式运行已构建的产物 |
| `pnpm lint` | 单独运行 ESLint |
| `pnpm typecheck` | 单独运行 TypeScript 类型检查 |

---

## 目录结构说明

```
frontend/
  src/
    app/                   # Next.js App Router 页面
      layout.tsx           # 根布局（QueryProvider + 全局样式）
      globals.css          # 全局样式 + CSS 变量 + 组件类
      page.tsx             # 首页，重定向到 /notebooks
      notebooks/
        page.tsx           # Notebook 列表页
        [id]/
          page.tsx         # Notebook 工作区（三栏布局）
      library/
        page.tsx           # Library 文档管理页
    components/
      layout/              # 布局组件（AppShell 可拖拽三栏）
      notebooks/           # Notebook 工作区协调组件
      sources/             # 文档源面板（SourceList / SourceCard）
      reader/              # 文档阅读器（MarkdownViewer / SelectionMenu）
      chat/                # 聊天面板（ChatPanel / ChatInput / MessageItem / ExplainCard）
      studio/              # Studio 面板（占位）
      providers/           # React Query Provider
    lib/
      api/                 # API 客户端模块（fetch 封装 + 类型定义）
      hooks/               # 自定义 Hooks（useChatSession / useChatStream / useTextSelection）
      utils/               # SSE 解析器、来源数据标准化等工具函数
    stores/                # Zustand 状态管理（ui-store / reader-store / chat-store）
    styles/
      markdown-content.css # Markdown 内容区排版样式
```

---

## 常见问题

**页面数据加载失败**

确认后端服务已在 `localhost:8000` 启动。前端所有 API 请求均通过 Next.js 代理转发，后端未运行时 API 会返回 502 错误，页面显示为空状态。

**pnpm 命令未找到**

```bash
npm install -g pnpm
```

安装后重新打开终端执行命令。

**端口 3000 被占用**

```bash
pnpm dev -- --port 3001
```

或先终止占用端口的进程后重新启动。

**构建出现类型错误**

单独运行类型检查查看详细信息：

```bash
pnpm typecheck
```
