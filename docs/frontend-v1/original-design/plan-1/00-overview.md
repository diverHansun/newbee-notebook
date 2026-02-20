# 前端开发总体规划

## 1. 文档说明

本文档为 Newbee Notebook 前端开发的总体规划文档，确立技术决策、模块划分、文档组织方式和开发优先级。后续各模块的详细设计文档均以本文档为基准展开。

本规划基于以下输入：
- 已有前端设计文档（frontend-v1/original-design/01~03）
- 后端 API 端点定义（postman_collection.json）
- 竞品参考项目（Open-Notebook、PageLM）
- Markdown 渲染参考项目（markdown-viewer-extension）
- MinerU 文档转换后的实际存储结构

---

## 2. 已确认的技术决策

以下决策已在讨论中确认，不再重复论证。

| 决策项 | 方案 | 说明 |
|--------|------|------|
| Markdown 渲染 | unified/remark/rehype 管线 + rehype-react | 借鉴 markdown-viewer-extension 的管线架构，支持 GFM、数学公式、代码高亮、CJK 排版 |
| 代码高亮 | highlight.js（通过 rehype-highlight） | 轻量、运行时高亮，覆盖常用语言。不使用 shiki（体积大、编辑器级精度非必需） |
| 图片加载 | 后端保存时路径转换 + Next.js 代理 | 后端 `save_markdown()` 在文档处理阶段已将 Markdown 中的相对图片路径转换为 API 绝对路径（`/api/v1/documents/{id}/assets/images/{hash}.jpg`）。前端无需做路径转换，浏览器直接加载，经 Next.js rewrites 代理到后端 |
| 长文档性能 | content-visibility: auto | MVP 阶段使用 CSS 懒渲染，不引入虚拟滚动，后续按需升级 |
| 主题系统 | light/dark 双主题 | 基于 CSS 变量实现，架构上预留主题扩展能力，但 MVP 只实现两套 |
| Markdown 排版风格 | VS Code / Cursor 内置 Markdown Preview | 不走学术期刊风格，参照 VS Code/Cursor 的 Markdown 预览排版 |
| explain/conclude 展示 | 独立浮动卡片 | 可拖动、可调整大小、可折叠的小窗口，不与 chat/ask 消息混合展示 |
| 存储演进 | 当前 Bind Mount，后续 MinIO | 前端无感，后端 ContentService 在读取时做路径转换。迁移在 frontend-v1 完成后进行 |

以下技术栈沿用 original-design 中的选型（01-tech-stack.md），不做变更：
- Next.js 15 (App Router) + TypeScript 5 + React 19
- shadcn/ui + Radix UI + Tailwind CSS 4
- Zustand（客户端状态） + TanStack Query（服务端状态）
- 原生 fetch + ReadableStream（SSE 流式）
- pnpm + ESLint + Prettier

---

## 3. 模块划分

前端按功能职责划分为以下模块。每个模块是一个内聚的功能单元，有明确的输入输出边界。

### 3.1 模块清单

| 模块 | 目录范围 | 核心职责 |
|------|----------|----------|
| A. 布局与路由 | `app/`, `components/layout/` | 三栏布局、响应式适配、路由结构、面板折叠与调整 |
| B. 文档源面板 | `components/sources/` | 文档列表展示、文档上传、处理状态跟踪、文档删除 |
| C. Markdown 查看器 | `components/reader/` | Markdown 渲染管线、代码高亮、数学公式、CJK 排版 |
| D. 文本选择交互 | `components/reader/` (部分) | 文本选中检测、浮动菜单、explain/conclude 模式触发 |
| E. 聊天系统 | `components/chat/` | SSE 流式通信、多会话管理、四种聊天模式、消息历史、来源引用 |
| F. 状态管理与 API 层 | `stores/`, `lib/api/`, `lib/hooks/` | Zustand 状态定义、TanStack Query 封装、API 请求函数、SSE 解析 |
| G. 主题与样式 | `styles/`, `app/globals.css` | CSS 变量主题系统、light/dark 切换、Markdown 内容排版样式 |
| H. Notebook 管理 | `app/notebooks/`, `components/notebooks/` | Notebook 列表、创建、编辑、删除、Library 管理页面 |

### 3.2 模块依赖关系

```
H. Notebook 管理 ──→ A. 布局与路由
                  ──→ F. 状态管理与 API 层

B. 文档源面板 ──→ F. 状态管理与 API 层

C. Markdown 查看器 ──→ G. 主题与样式
                    ──→ F. 状态管理与 API 层（获取文档内容）

D. 文本选择交互 ──→ C. Markdown 查看器（在其渲染区域内工作）
                  ──→ E. 聊天系统（触发 explain/conclude 消息）

E. 聊天系统 ──→ F. 状态管理与 API 层
```

---

## 4. 模块复杂度分析

### 4.1 复杂度评估

| 模块 | 复杂度 | 核心难点 |
|------|--------|----------|
| A. 布局与路由 | 中 | 三栏可调宽度、响应式断点切换（三栏/双栏/标签页）、面板折叠状态持久化 |
| B. 文档源面板 | 低-中 | 文件上传（multipart）、处理状态轮询、列表分页 |
| C. Markdown 查看器 | **中-高** | unified 管线搭建、GFM/数学公式/代码高亮集成、CJK 排版、长文档性能。无需自定义插件（图片路径由后端在保存时转换） |
| D. 文本选择交互 | 中 | Selection API 兼容性、菜单定位计算、选中文本与文档 ID 的上下文关联 |
| E. 聊天系统 | **高** | SSE 流式解析与增量渲染、四种模式（chat/ask/explain/conclude）的请求构建、多会话切换、流式取消、来源引用展示 |
| F. 状态管理与 API 层 | 中 | Store 设计（避免状态冗余）、TanStack Query 缓存策略、SSE 流解析工具函数 |
| G. 主题与样式 | 低-中 | CSS 变量体系设计、Markdown 内容区排版样式（标题/表格/代码块/引用块/列表） |
| H. Notebook 管理 | 低 | 标准 CRUD 页面、表单交互 |

### 4.2 需要详细设计文档的模块

根据复杂度评估，以下模块需要完整的设计文档（goals-duty → architecture → dfd-interface）：

1. **C. Markdown 查看器** — 最高优先级
   - unified 管线的插件选型与组装顺序
   - Markdown 内容区的 CSS 排版规范
   - 与后端 `/documents/{id}/content` 端点的数据对接

2. **E. 聊天系统** — 最高优先级
   - SSE 流式响应的解析状态机
   - 四种模式的请求参数差异与 UI 差异
   - 多会话的状态管理策略
   - 流式取消机制
   - 消息中来源引用的展示与跳转

以下模块以简化形式记录（goals-duty + 关键设计说明），不需要完整文档链：

3. **A. 布局与路由** — 三栏布局的断点策略和面板交互
4. **F. 状态管理与 API 层** — Store 划分和 API 封装模式
5. **D. 文本选择交互** — Selection API 使用和上下文传递

以下模块复杂度较低，在开发时参照 original-design 已有文档即可，不单独撰写：

6. **B. 文档源面板**
7. **G. 主题与样式**
8. **H. Notebook 管理**

---

## 5. 文档组织方式

```
plan-1/
  00-overview.md                      ← 本文档
  01-markdown-viewer/
    goals-duty.md                     ← 模块目标与职责
    architecture.md                   ← 渲染管线架构
    dfd-interface.md                  ← 数据流与接口
  02-chat-system/
    goals-duty.md
    architecture.md
    dfd-interface.md
  03-layout-and-routing.md            ← 简化文档（单文件）
  04-state-and-api.md                 ← 简化文档（单文件）
  05-text-selection.md                ← 简化文档（单文件）
  06-page-flows-and-interactions.md   ← 页面流程与交互设计（首页、Library、上传、轮询、错误处理）
```

文档编写遵循 docs-plan 指南的核心原则：
- 按 goals-duty → architecture → dfd-interface 顺序撰写
- 每份文档聚焦模块级别，不涉及项目级全貌
- 描述设计意图与职责边界，不写具体实现代码
- 设计决策附带理由，标注已放弃的替代方案
- 允许演进，不使用绝对化表述

---

## 6. 开发阶段划分

| 阶段 | 模块 | 产出 | 前置条件 |
|------|------|------|----------|
| Phase 1 | A. 布局与路由 + G. 主题与样式 | 项目骨架、三栏布局、首页布局、主题切换、API 代理配置 | 无 |
| Phase 2 | H. Notebook 管理 + Library 页面 | 首页 Notebook 列表/创建、Library 文档管理、文档上传 | Phase 1 |
| Phase 3 | B. 文档源面板 | 添加文档 Sheet、文档状态轮询、SourceCard 状态展示 | Phase 2 |
| Phase 4 | C. Markdown 查看器 | unified 管线、内容排版 | Phase 1 |
| Phase 5 | F. 状态管理与 API 层 + E. 聊天系统 | SSE 流式、Session 选择器、chat/ask 模式切换、ExplainCard | Phase 3, 4 |
| Phase 6 | D. 文本选择交互 | 选中文本、浮动菜单、explain/conclude | Phase 4, 5 |
| Phase 7 | 联调与优化 | 端到端测试、错误处理完善、性能调优、响应式 | Phase 1-6 |

---

## 7. 后端 API 端点映射

前端各模块所依赖的后端 API 端点汇总，便于开发时快速定位。

### Notebook 管理 (H)
- `POST /notebooks` — 创建
- `GET /notebooks` — 列表（分页）
- `GET /notebooks/{id}` — 详情
- `PATCH /notebooks/{id}` — 更新
- `DELETE /notebooks/{id}` — 删除

### Library 管理
- `GET /library` — Library 信息（document_count）
- `POST /documents/library/upload` — 上传文件到 Library（multipart/form-data，支持多文件）
- `GET /library/documents` — Library 文档列表（分页、status 过滤：uploaded|pending|processing|completed|failed）
- `DELETE /library/documents/{id}` — 软删除（移除索引+数据库，保留磁盘文件）
- `DELETE /library/documents/{id}?force=true` — 硬删除（彻底删除）

### 文档源面板 (B)
- `POST /notebooks/{id}/documents` — 将 Library 文档关联到 Notebook（body: document_ids[]，触发处理）
- `GET /notebooks/{id}/documents` — Notebook 内文档列表（分页）
- `DELETE /notebooks/{id}/documents/{did}` — 解除关联（仅删除引用关系）
- `GET /documents/{id}` — 文档元数据与处理状态（用于轮询）

### Markdown 查看器 (C)
- `GET /documents/{id}/content?format=markdown` — 获取 Markdown 内容
- `GET /documents/{id}/download` — 下载原始文件
- `GET /documents/{id}/assets/{path}` -- 图片等资源文件（Markdown 中已包含绝对路径，通过 Next.js rewrites 代理）

### 聊天系统 (E)
- `POST /notebooks/{id}/sessions` — 创建会话
- `GET /notebooks/{id}/sessions` — 会话列表
- `GET /notebooks/{id}/sessions/latest` — 最新会话
- `GET /sessions/{id}` — 会话详情
- `DELETE /sessions/{id}` — 删除会话
- `GET /sessions/{id}/messages` — 消息历史（分页、模式过滤）
- `POST /chat/notebooks/{id}/chat` — 非流式聊天
- `POST /chat/notebooks/{id}/chat/stream` — SSE 流式聊天
- `POST /chat/stream/{message_id}/cancel` — 取消流式响应

### Admin（前端部分场景需要）
- `POST /admin/documents/{id}/reindex?force=true` — 重新处理失败的文档
- `POST /admin/reprocess-pending` — 批量触发处理
- `GET /admin/index-stats` — 文档状态统计

### 系统
- `GET /health` / `GET /health/ready` / `GET /health/live` — 健康检查
- `GET /info` — 系统信息（版本号、支持的功能模块和聊天模式）

---

## 8. SSE 事件格式（已确认）

后端 SSE 流式端点返回的事件格式，每个事件为一行 `data: {JSON}\n\n`。

| 事件类型 | 数据结构 | 说明 |
|----------|----------|------|
| start | `{"type": "start", "message_id": int}` | 流开始，返回后端分配的消息 ID |
| content | `{"type": "content", "delta": string}` | 增量内容片段，追加到当前消息 |
| sources | `{"type": "sources", "sources": [...]}` | RAG 来源引用数组 |
| done | `{"type": "done"}` | 流正常结束 |
| error | `{"type": "error", "error_code": string, "message": string}` | 错误信息 |
| heartbeat | `{"type": "heartbeat"}` | 心跳保活，每 15 秒一次 |

前端 SSE 解析器需要：
- 使用原生 fetch + ReadableStream（因后端端点为 POST 请求，EventSource 不支持）
- 维护文本缓冲区，按 `\n\n` 分割完整事件
- 过滤 heartbeat 事件，不传递给上层
- 通过 AbortController 支持流取消
