# 布局与路由 -- 设计说明

---

## 1. 设计目标

提供应用的页面骨架结构：首页 Notebook 列表页（单栏）、Library 管理页（单栏）、Notebook 详情页（三栏可调布局），支持响应式断点切换和面板状态管理。

---

## 2. 职责

- 实现三栏布局（Sources Panel / Main Panel / Studio Panel），各栏宽度可通过拖拽分隔条调整
- 响应式断点切换：大屏（>1024px）三栏并排，中屏（640-1024px）隐藏 Studio 显示两栏，小屏（<640px）单栏加底部标签页切换
- 面板折叠：Sources Panel 和 Studio Panel 可折叠为窄条，折叠状态持久化到 localStorage
- 路由结构管理（基于 Next.js App Router）
- API 代理配置：通过 Next.js rewrites 将 `/api/v1/*` 代理到后端

---

## 3. 非职责

- 不管理面板内部的具体内容（各面板内容由对应模块负责）
- 不处理认证和权限逻辑

---

## 4. 路由结构

```
/                            → 重定向到 /notebooks
/notebooks                   → Notebook 列表页
/notebooks/[id]              → Notebook 详情页（三栏布局）
/library                     → Library 文档管理页
```

Notebook 详情页是三栏布局的唯一使用场景。列表页和 Library 页使用常规单栏布局。各页面的详细交互设计见 `06-page-flows-and-interactions.md`。

---

## 5. 三栏布局的关键设计

### 5.1 面板宽度

| 面板 | 默认宽度 | 最小宽度 | 最大宽度 |
|------|----------|----------|----------|
| Sources Panel | 25% | 240px | 40% |
| Main Panel | 50% | 360px | 无限制 |
| Studio Panel | 25% | 240px | 40% |

使用 Radix UI 的 `react-resizable-panels` 实现面板拖拽调整。面板宽度比例持久化到 localStorage。

### 5.2 Main Panel 的视图模式

Main Panel 内部支持多种视图：

- **Chat View**：聊天面板占满 Main Panel（默认）
- **Reader View**：Markdown 查看器占满 Main Panel（从 Sources Panel 点击"查看"文档触发）
- **Split View**（可选，后续迭代）：上下分屏，上方 Markdown 查看器，下方聊天面板

视图模式由 UI 状态管理，不影响路由。

### 5.3 面板折叠交互

- 折叠时面板收缩为 40px 窄条，显示展开按钮
- 展开时恢复到折叠前的宽度
- 折叠状态通过 Zustand store 管理并持久化

---

## 6. Next.js 配置要点

### 6.1 API 代理

```
next.config.ts rewrites:
  /api/v1/:path* → http://localhost:8000/api/v1/:path*
```

这确保前端所有 API 请求和图片资源请求都通过 Next.js 转发，避免跨域问题。

### 6.2 App Router 结构

```
app/
  layout.tsx                 -- 根布局（ThemeProvider, QueryProvider）
  page.tsx                   -- 首页重定向
  notebooks/
    page.tsx                 -- Notebook 列表
    [id]/
      page.tsx               -- Notebook 详情（三栏布局）
      layout.tsx             -- 详情页布局（含面板状态管理）
  library/
    page.tsx                 -- Library 管理
```
