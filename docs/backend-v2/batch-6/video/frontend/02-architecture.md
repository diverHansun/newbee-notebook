# Video 前端模块：架构设计

## 1. 架构总览

Video 前端模块位于 Studio 面板内，与 Notes、Diagrams 并列。其核心职责是接收用户操作、调用后端 API、以合理的方式渲染数据和状态变化。

```
StudioPanel (studio-panel.tsx)
    │
    ├── Home 视图
    │       └── Video 卡片（第二行，保持 2 列网格）
    │
    ├── Videos 视图（videos view）
    │       │
    │       ├── VideoInputArea        # URL 输入 + 登录状态 + step indicator
    │       │       ├── BilibiliLoginButton    # 未登录时显示登录入口
    │       │       └── SummarizeProgress      # 进度区域内联错误时显示
    │       │
    │       └── VideoListView        # 历史摘要列表（缩略图 + 文字）
    │               └── VideoListItem
    │
    └── VideoDetail 视图（video-detail view）
            │
            ├── VideoInfoHeader       # 缩略图、标题、UP主、时长、平台
            │
            ├── VideoSummaryContent   # Markdown 渲染的摘要内容
            │
            └── VideoActionBar       # 关联 notebook、复制、删除
```

两条数据通道的汇合点在 TanStack Query 缓存：无论总结是通过面板 SSE 完成还是通过 agent 工具调用完成，最终都会使相关 query key 失效，Video 面板自动重新拉取并展示最新数据。

## 2. 组件设计

### 2.1 组件组织方式

选择「独立组件 + 适度重构」方式。将 Video 相关视图抽取为独立文件：

- `video-list.tsx` -- Videos 视图（videos view）
- `video-detail.tsx` -- VideoDetail 视图（video-detail view）
- `video-input-area.tsx` -- 输入区域组件（含 step indicator 和登录状态）
- `video-list-item.tsx` -- 列表条目组件

这些组件在 `studio-panel.tsx` 中通过条件渲染方式挂载：

```typescript
{studioView === "videos" ? <VideoListView notebookId={notebookId} /> : null}
{studioView === "video-detail" ? <VideoDetailView notebookId={notebookId} /> : null}
```

选择条件渲染而非路由的好处是：Video 视图是 Studio 面板的子面板而非独立页面，不需要 URL 层面的路由隔离。视图切换由 studio-store 管理，与 Notes、Diagrams 的模式一致。

### 2.2 Step Indicator 组件

Step Indicator 嵌入在 `VideoInputArea` 内部，在总结过程中替换输入区域下方或其中的内容。组件接收一个 `steps: string[]` 和当前 `currentStep: number` props，渲染为竖直或水平的步骤列表，当前步骤高亮，已完成步骤打勾或变灰。

错误状态时，在 step indicator 下方渲染红色错误文字和重试按钮。

### 2.3 BilibiliLoginButton 组件

位于 `VideoInputArea` 内部，与 URL 输入框和总结按钮并列展示。状态：

- 未登录：显示「B站登录」文字按钮，点击后弹出 QR 码弹窗
- 登录中：显示加载状态
- 已登录：显示用户名或头像缩略图，点击可登出或刷新状态

## 3. 状态管理

### 3.1 全局导航状态（studio-store.ts）

扩展 `StudioView` 类型：

```typescript
export type StudioView = "home" | "notes" | "note-detail" | "diagrams" | "diagram-detail" | "videos" | "video-detail";
```

新增状态和方法：

```typescript
activeVideoId: string | null;
openVideoDetail: (videoId: string) => void;
backToVideoList: () => void;
```

所有 Video 导航状态与其他 skill（Notes、Diagrams）的状态放在同一个 store 中，保持面板级别的状态集中管理。

### 3.2 组件级临时状态

以下状态不属于全局 store，而是组件内部的 `useState`：

- 输入框的值（inputValue）
- 当前总结进度步骤（currentStep、steps）
- 错误信息（error）
- 登录弹窗的开关状态（loginDialogOpen）
- 确认删除弹窗的状态（pendingDeleteVideoId）
- 列表筛选器（filterMode: "all" | "current-notebook"）

这样做的好处是：这些状态只在用户与当前组件交互时有用，不需要跨组件共享。

### 3.3 SSE 进度状态

SSE 连接状态（正在连接、接收中、已完成、错误）作为 `VideoInputArea` 组件的局部状态管理。当 SSE 连接建立时，进入「总结中」状态，UI 切换为 step indicator；当收到 `done` 或 `error` 事件时，复原为可输入状态。

## 4. 设计模式

### 4.1 API Client 模式

Video 模块的 API client 函数遵循 `lib/api/` 中现有模式。以 `apiFetch` 为底层 HTTP client，按功能划分为独立文件：

- `lib/api/videos.ts` -- VideoSummary 的 CRUD、总结触发
- `lib/api/bilibili-auth.ts` -- B站登录状态查询、登出

每个函数对应一个后端 API 端点，返回类型化的 Promise。

### 4.2 TanStack Query Hooks 模式

遵循 `lib/hooks/use-diagrams.ts` 确立的模式：

- 导出 `QUERY_KEY` 常量工厂函数
- 每个 query 有独立的 hook（`useVideoSummaries`、`useVideoSummary`）
- 每个 mutation 有独立的 hook，内部处理缓存失效

Video 模块提供两个列表 query hook：

- `useAllVideoSummaries()` -- 查询用户全部摘要（默认视图）
- `useVideoSummaries(notebookId)` -- 查询当前 notebook 已关联的摘要

详情 query：`useVideoSummary(summaryId)`

Mutation hooks：`useCreateVideoSummary`、`useDeleteVideoSummary`、`useAssociateVideoSummary`、`useDisassociateVideoSummary`。

### 4.3 SSE 消费模式

使用 `fetch` + `ReadableStream` 手动解析 SSE，与 bilibili-summary 项目和现有 chat SSE 消费方式一致。

```typescript
const response = await fetch(url, { method: "POST", headers, body });
const reader = response.body.getReader();
// 循环读取 SSE 事件并解析
```

不使用 `EventSource`，因为需要支持 POST 请求和自定义 header。

### 4.4 Markdown 渲染

复用现有的 Markdown 渲染组件（`react-markdown` 或项目已有的方案），不引入新的渲染依赖。渲染配置与 chat 消息保持一致。

## 5. 模块结构与文件布局

```
frontend/src/
├── components/studio/
│       ├── video-list.tsx              # Videos 视图（列表 + 输入区）
│       ├── video-detail.tsx            # VideoDetail 视图
│       ├── video-input-area.tsx        # URL 输入 + step indicator + 登录按钮
│       ├── video-list-item.tsx         # 列表条目（缩略图 + 文字）
│       ├── video-info-header.tsx       # 详情页视频信息头
│       └── video-action-bar.tsx        # 详情页操作栏（关联/删除）
│
├── lib/api/
│       ├── videos.ts                   # VideoSummary CRUD + 总结触发 API
│       └── bilibili-auth.ts            # B站登录状态、登出 API
│
├── lib/hooks/
│       ├── use-videos.ts               # TanStack Query hooks（列表 + 详情）
│       └── use-bilibili-auth.ts        # B站登录状态 hook
│
├── lib/i18n/
│       └── strings.ts                   # 新增 video 命名空间 + slashCommand/confirmation 补充
│
├── stores/
│       └── studio-store.ts              # 扩展 StudioView + activeVideoId + nav 方法
│
└── components/chat/
        └── slash-command-hint.tsx       # 新增 /video 命令条目
```

## 6. 架构约束与权衡

### 6.1 条件渲染而非路由

选择条件渲染而非 React Router 的原因：

- Video 视图是 Studio 面板的子视图，不是独立页面
- Studio 面板已经有完整的状态管理（studio-store），视图切换通过 `studioView` 状态驱动
- 不需要 URL 层面的 deep link 支持

代价是用户无法通过浏览器后退键在 Video 列表和详情之间导航，这在 Studio 面板场景下可接受。

### 6.2 SSE 进度局部状态

SSE 连接和进度状态不放入全局 store，而是在 `VideoInputArea` 组件内通过 `useState` 管理。这样做的好处是：

- SSE 连接与特定输入实例绑定，不存在跨组件竞争
- 组件卸载时自然清理连接，不需要额外的 store 清理逻辑

如果后续需要在 agent chat 界面也展示 Video 进度（例如通过工具调用触发时），可以将 SSE 状态提升到 chat-store，但这需要额外的设计讨论。

### 6.3 不实现 Video 的懒加载列表

第一阶段不实现分页加载，所有摘要一次性加载。理由：

- 用户个人视频摘要数量在初期不会很大
- 降低实现复杂度

如果后续需要支持大量摘要，可以升级为分页 query（使用 `offset`/`limit` 参数）。
