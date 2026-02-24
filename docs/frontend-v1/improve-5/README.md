# Frontend V1 Improve-5 阶段

## 阶段目标

在 improve-4（工程可维护性、国际化、智能引用、性能优化）的基础上，本阶段聚焦于 **全局控制面板建设、Notebook 列表体验优化、交互细节修复** 三个维度。

核心改动：将分散在各页面的语言切换控件统一收纳到一个全局控制面板中，同时新增主题切换和系统信息展示，并为模型配置、RAG 参数调节等功能预留入口（后端 API 在 backend-v2 阶段实施）；优化 Notebook 卡片尺寸与分页机制；修复 Sources 面板"刷新"按钮的交互反馈缺失。

## 问题清单

| 编号 | 问题 | 类型 | 复杂度 | 优先级 |
|------|------|------|--------|--------|
| P1 | 语言切换仅在 Notebook 详情页，其他页面无入口，体验不一致 | 全局交互 | 中高 | P0 |
| P2 | Notebook 卡片过小，无分页管理 | 页面布局 | 中 | P1 |
| P3 | Sources 面板"刷新"按钮缺少 hover/active 交互反馈 | 交互细节 | 低 | P2 |

## 实施顺序

```
P1 (全局控制面板 — 含语言切换迁移、主题切换、系统信息；模型/RAG/MCP/Skills 占位)
      |
P2 (Notebook 卡片增强与分页)  ←── 可与 P1 并行
      |
P3 (刷新按钮交互修复)  ←── 独立，随时可做
```

> P1 是本阶段核心工作量，涉及新组件开发和全局布局调整。模型配置和 RAG 设置的后端 API 及前端交互实现推迟到 backend-v2 阶段，improve-5 中以占位形式展示。P2 和 P3 相对独立，可并行推进。

## 推荐实施批次

| 批次 | 任务 | 验证重点 |
|------|------|---------|
| **批次 A** | P3 刷新按钮修复 | 目视验证 hover 背景色变化 + active 缩放效果，与"+添加"按钮行为一致 |
| **批次 B** | P1 全局控制面板（分步：Icon 组件 -> Popover 骨架 -> 语言模块 -> 主题模块 -> 占位模块 -> 关于模块） | 所有页面左下角可见 Icon；点击弹出 Split Popover；语言切换从 header 迁移至面板；主题切换即时生效；模型/RAG/MCP/Skills 以占位展示；关于面板显示版本和连接状态 |
| **批次 C** | P2 卡片增强与分页 | 卡片视觉增大（minmax 320px）；分页控件在 notebook 数量超过 12 时出现；翻页后数据正确加载；创建后跳转到第一页 |

## 测试与验收策略

### 前端静态检查

- `pnpm typecheck`：TypeScript 类型检查（每批次必做）
- `pnpm build`：批次 B 完成后必做，确认新组件不影响构建

### 功能验证（Playwright 手动/脚本化）

- **P1**：三个页面（Notebooks、Library、Notebook 详情）均可见控制面板 Icon；语言切换在面板中操作后全局生效；原 header 中语言切换已移除；主题切换即时生效且刷新后保持；模型/RAG/MCP/Skills 菜单项以占位展示且不可点击；关于面板显示版本号和后端连接状态
- **P2**：创建超过 12 个 notebook 后触发分页；翻页后卡片内容正确；删除至当前页为空时自动退回前一页
- **P3**：hover 刷新按钮时出现背景色变化；点击时有缩放反馈

### 回归验证

- 语言切换功能迁移后，`localStorage` 持久化行为不变
- 已有的 CSS 模块化结构不被破坏（新增样式文件遵循既有拆分规范）

## 设计约束

- **向后兼容**：语言切换迁移后，`useLang()` hook 接口不变，所有已迁移的 i18n 调用无需修改
- **最小侵入**：控制面板作为独立组件挂载在根布局层，不修改现有页面组件内部逻辑
- **渐进增强**：模型配置和 RAG 参数的后端 API 和前端交互在 backend-v2 阶段实施，improve-5 中以占位形式展示
- **确认后保存**（backend-v2 阶段）：模型和 RAG 配置修改需用户点击"应用更改"按钮确认后才持久化写入后端，不自动保存
- **MCP/Skills/模型/RAG 占位**：控制面板左侧菜单预留这四个入口，以 "即将推出" 状态展示，improve-5 不实现具体功能

## 文档索引

| 文件 | 内容 |
|------|------|
| [P1-global-control-panel.md](P1-global-control-panel.md) | 全局控制面板（Split Popover）设计方案：ThemeProvider 架构、占位菜单；含 backend-v2 阶段的模型/RAG 确认保存 UX 设计参考 |
| [P2-notebook-cards-pagination.md](P2-notebook-cards-pagination.md) | Notebook 卡片尺寸增大与分页管理 |
| [P3-refresh-button-fix.md](P3-refresh-button-fix.md) | Sources 面板刷新按钮交互修复 |

## 涉及的主要文件

### 前端 — 新增

- `frontend/src/lib/theme/theme-context.tsx` — ThemeProvider + useTheme hook（与 LanguageProvider 对称的 Context 模式）
- `frontend/src/components/layout/control-panel.tsx` — 全局控制面板主组件（Split Popover）
- `frontend/src/components/layout/control-panel-icon.tsx` — 左下角 Icon 组件
- `frontend/src/styles/control-panel.css` — 控制面板样式

### 前端 — 修改

- `frontend/src/app/layout.tsx` — 挂载全局控制面板 Icon
- `frontend/src/components/providers/app-provider.tsx` — 新增 ThemeProvider 包裹层
- `frontend/src/components/layout/app-shell.tsx` — 移除 header 中的语言切换控件
- `frontend/src/app/notebooks/page.tsx` — 卡片布局增大、分页逻辑
- `frontend/src/components/sources/source-list.tsx` — 刷新按钮样式类名调整
- `frontend/src/styles/layout.css` — `.notebook-grid` 列宽从 280px 增至 320px
- `frontend/src/styles/cards.css` — `.card` 内边距和最小高度调整
- `frontend/src/styles/buttons.css` — ghost 按钮交互增强（可选）
- `frontend/src/app/globals.css` — 新增 control-panel.css 的 @import
- `frontend/src/lib/i18n/strings.ts` — 新增控制面板 + 分页相关 i18n 文本

### 后端 — 不涉及（improve-5 阶段）

improve-5 不新增后端代码。以下已有端点供「关于」面板读取，无需改动：

- `GET /api/v1/info` — 版本信息
- `GET /api/v1/health` — 健康检查

### 后端 — backend-v2 阶段新增

- `newbee_notebook/api/routers/settings.py` — Settings API 路由（4 个端点：GET/PUT models, GET/PUT rag），详见 [P1 后端 API 设计](P1-global-control-panel.md#模块三模型配置backend-v2-阶段实施)
- `frontend/src/lib/api/settings.ts` — 前端 Settings API 调用层（与后端 API 同步创建）
